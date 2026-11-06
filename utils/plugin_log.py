"""Bounded plugin logging with native-style records and independent crash writes."""

import asyncio
import contextvars
import hashlib
import itertools
import logging
import queue
import re
import sys
import threading
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LEVELS = {
    "TRACK": 5,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
SHORT_LEVELS = {5: "TRACK", 10: "DBUG", 20: "INFO", 30: "WARN", 40: "ERRO", 50: "CRIT"}
EVENT_NAMES = {
    "runtime.start": "Humanization started",
    "runtime.stop": "Humanization stopped",
    "runtime.initialize.failed": "Humanization initialization failed",
    "gate.start": "Controller started",
    "gate.complete": "Controller completed",
    "gate.failed": "Controller failed",
    "gate.cancelled": "Controller cancelled",
    "summary.start": "Recorder started",
    "summary.complete": "Recorder completed",
    "summary.failed": "Recorder failed",
    "summary.cancelled": "Recorder cancelled",
    "reply.start": "Reply started",
    "reply.complete": "Reply completed",
    "reply.failed": "Reply failed",
    "model.complete": "Model call completed",
    "admin.log.cleared": "Plugin log cleared",
    "track.call": "Function entered",
    "track.return": "Function returned",
    "track.error": "Function raised",
}
# These are diagnostic labels, never arbitrary user-authored strings.
PUBLIC_FIELDS = {
    "action",
    "status",
    "purpose",
    "provider",
    "mode",
    "trigger",
    "emotion",
    "participation",
    "error_type",
    "caller",
    "target",
    "function",
    "return_summary",
    "level",
    "cache_source",
    "accounting",
    "diary_date",
    "date",
    "source",
}


class NativeFormatter(logging.Formatter):
    """Format the local file like AstrBot without installing global handlers."""

    def __init__(self, timezone):
        super().__init__()
        self.timezone = timezone

    def format(self, record):
        stamp = datetime.fromtimestamp(record.created, self.timezone).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]
        source = Path(record.pathname)
        location = f"{source.parent.name}.{source.stem}:{record.lineno}"
        version = ""
        if record.levelno >= logging.WARNING:
            from astrbot.core.config.default import VERSION

            version = f"[v{VERSION}]"
        trace = f" [id={record.operation}]" if record.operation else ""
        return (
            (
                f"[{stamp}] [astrbot_plugin_humanization] "
                f"[{SHORT_LEVELS[record.levelno]}]{version} [{location}]{trace}: "
                f"{record.getMessage()}"
            )
            .replace("\r\n", "\n")
            .replace("\n", "\r\n")
        )


class FileHandler(RotatingFileHandler):
    """Use byte-based rotation, CRLF and caller-controlled write failure recovery."""

    def _open(self):
        return open(self.baseFilename, self.mode, encoding="utf-8", newline="")

    def shouldRollover(self, record):
        if not self.maxBytes:
            return False
        if self.stream is None:
            self.stream = self._open()
        self.stream.seek(0, 2)
        return (
            self.stream.tell() > 0
            and self.stream.tell()
            + len((self.format(record) + self.terminator).encode("utf-8"))
            > self.maxBytes
        )

    def handleError(self, record):
        # Let the owner fall back without logging the same error recursively.
        raise


class PluginLog:
    """Write one plugin stream independently of the host's event loop.

    Args:
        directory: Dedicated plugin log directory.
        debug: Unlock TRACK instrumentation; does not select DEBUG verbosity.
        console: AstrBot plugin logger, never reconfigured here.
        timezone: Timestamp timezone.
        level: Local minimum severity.
        mask: Mask identities and free text in both outputs.
        echo: Forward sanitized records to the host.
        max_mb: Active file limit in MiB; zero disables rotation.
    """

    _credential_key = re.compile(
        r"(?:^key$|api[_-]?key|access[_-]?key|private[_-]?key|token|jwt|password|passwd|secret|authorization|cookie|credential|密钥|令牌|密码)",
        re.I,
    )
    _credential_text = re.compile(
        r"""(?i)(\b(?:api[_-]?key|access[_-]?key|private[_-]?key|key|access[_-]?token|token|jwt|password|passwd|secret|authorization|cookie|credential|密钥|令牌|密码)\b["']?\s*[:=]\s*["']?)([^\s"',;}]+)"""
    )
    _bearer = re.compile(r"""(?i)\bBearer\s+[^\s"',;}]+""")
    _key_token = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
    _binary_key = re.compile(
        r"(?:base64|binary|image_data|audio_data|video_data)$", re.I
    )
    _data_uri = re.compile(r"data:[^\s;,]+;base64,[A-Za-z0-9+/=]+", re.I)
    _umo = re.compile(r"([^\s:]+:(?:GroupMessage|FriendMessage):)([^\s,;]+)")

    def __init__(
        self,
        directory: Path,
        debug: bool,
        console,
        timezone,
        *,
        level="INFO",
        mask=False,
        echo=False,
        max_mb=10,
    ):
        self.directory = directory
        self.console = console
        self.timezone = timezone
        self.debug_mode = debug
        self.level = "INFO" if level == "TRACK" and not debug else level
        self.mask = mask
        self.echo = echo
        self.max_bytes = max(1, int(max_mb * 1024**2)) if max_mb else 0
        self.queue = queue.Queue(maxsize=1024)
        self.trace = contextvars.ContextVar("humanization_log_trace", default="")
        self.usage = contextvars.ContextVar("humanization_log_usage", default=None)
        self.worker = None
        self.handler = None
        self.closed = False
        self.io_reported = False
        self.dropped = 0
        self.lock = threading.RLock()
        self.tracker = None

    def enabled(self, level):
        return LEVELS[level] >= LEVELS[self.level] and not self.closed

    async def open(self):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self.handler = FileHandler(
                self.directory / "humanization.log",
                maxBytes=self.max_bytes,
                backupCount=3,
                encoding="utf-8",
                delay=True,
            )
            self.handler.terminator = "\r\n"
            self.handler.setFormatter(NativeFormatter(self.timezone))
            # Verify the destination before reporting successful startup.
            self.handler.stream = self.handler._open()
        except OSError as exc:
            self._emergency(exc)
        self.worker = threading.Thread(
            target=self._write_loop, name="humanization-log-writer", daemon=True
        )
        self.worker.start()

    @asynccontextmanager
    async def context(self, prefix: str):
        """Correlate an operation and collect its auxiliary model counters.

        Args:
            prefix: Business operation category.
        """
        token = self.trace.set(f"{prefix}-{uuid.uuid4().hex[:8]}")
        counters = self.usage.set({})
        try:
            yield
        finally:
            try:
                self.usage.reset(counters)
                self.trace.reset(token)
            except ValueError:
                # Async-generator cleanup can run in a different context.
                self.usage.set(None)
                self.trace.set("")

    @staticmethod
    def identity(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def mask_text(value):
        size = len(value)
        if size < 2:
            return value
        if size == 2:
            return value[0] + "**"
        visible = max(2, round(size / 3))
        left = (visible + 1) // 2
        right = visible // 2
        return value[:left] + "*" * (size - visible) + value[-right:]

    @classmethod
    def redact(cls, value, depth=0):
        """Bound diagnostics and remove credentials before either output.

        Args:
            value: Diagnostic value; arbitrary objects are never stringified.
            depth: Current container depth.

        Returns:
            Bounded JSON-like data with credentials removed.
        """
        if isinstance(value, bytes):
            return f"bytes(length={len(value)})"
        if isinstance(value, str):
            value = value[:8192]
            value = cls._data_uri.sub("[BINARY OMITTED]", value)
            value = cls._bearer.sub("Bearer [REDACTED]", value)
            value = cls._key_token.sub("[REDACTED]", value)
            value = cls._credential_text.sub(r"\1[REDACTED]", value)
            return value
        if isinstance(value, (dict, list, tuple)):
            if depth >= 2:
                return f"{type(value).__name__}(count={len(value)})"
            if isinstance(value, dict):
                return {
                    str(key): "[REDACTED]"
                    if cls._credential_key.search(str(key))
                    and not (
                        str(key)
                        in {
                            "tokens_input",
                            "tokens_input_cached",
                            "tokens_output",
                            "tokens_total",
                        }
                        and (item is None or isinstance(item, (int, float)))
                    )
                    else f"binary(length={len(item)})"
                    if cls._binary_key.search(str(key))
                    and isinstance(item, (str, bytes))
                    else cls.redact(item, depth + 1)
                    for key, item in itertools.islice(
                        value.items(), 40 if depth == 0 else 8
                    )
                }
            return [cls.redact(item, depth + 1) for item in value[:8]]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return f"{type(value).__name__}(object)"

    def _value(self, key, value):
        if self.mask and key in ("sender_id", "user_id", "group_id", "session_id"):
            value = str(value)
        if isinstance(value, dict):
            return (
                "{"
                + ", ".join(f"{k}={self._value(k, v)}" for k, v in value.items())
                + "}"
            )
        if isinstance(value, list):
            return "[" + ", ".join(self._value(key, v) for v in value) + "]"
        if isinstance(value, str):
            if self.mask and value != "[REDACTED]":
                if self._umo.search(value):
                    value = self._umo.sub(lambda m: m[1] + self.mask_text(m[2]), value)
                    if key not in ("conversation", "umo", "session"):
                        value = self.mask_text(value)
                elif key not in PUBLIC_FIELDS:
                    value = self.mask_text(value)
            return value.replace("\r", "\\r").replace("\n", "\\n")[:180]
        return (
            str(value).lower()
            if value is None or isinstance(value, bool)
            else str(value)
        )

    def info(self, event, **fields):
        self._emit("INFO", event, fields)

    def debug(self, event, **fields):
        self._emit("DEBUG", event, fields)

    def warning(self, event, **fields):
        self._emit("WARNING", event, fields)

    def error(self, event, **fields):
        self._emit("ERROR", event, fields)

    def critical(self, event, **fields):
        self._emit("CRITICAL", event, fields, exception=True)

    def exception(self, event, **fields):
        self._emit("ERROR", event, fields, exception=True)

    def track(self, event, source, **fields):
        self._emit("TRACK", event, fields, source=source)

    def model_usage(self, **fields):
        """Attach auxiliary counters to the outcome; emit native steps separately."""
        usage = fields.pop("usage", None) or {}
        details = fields.pop("provider_details", None) or {}
        fields.update({f"tokens_{key}": value for key, value in usage.items()})
        fields.update({f"provider_{key}": value for key, value in details.items()})
        if (
            fields.get("purpose") in ("controller", "recorder")
            and self.usage.get() is not None
        ):
            self.usage.get().update(fields)
        else:
            self.info("model.complete", **fields)

    def _emit(self, level, event, fields, *, exception=False, source=None):
        if not self.enabled(level):
            return
        if event in (
            "gate.complete",
            "gate.failed",
            "summary.complete",
            "summary.failed",
        ):
            if counters := self.usage.get():
                fields = {**counters, **fields}
                counters.clear()
        if source is None:
            frame = sys._getframe(2)
            source = (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)
        if exception and (error := sys.exc_info()[1]) is not None:
            fields = {**fields, "error_type": type(error).__name__}
        data = self.redact(fields)
        text = EVENT_NAMES.get(
            event, event.replace(".", " ").replace("_", " ").capitalize()
        )
        text += f" ({event})"
        if data:
            text += ": " + " ".join(
                f"{key}={self._value(key, value)}" for key, value in data.items()
            )
        if exception and (exc := sys.exc_info()[1]) is not None:
            # Do not include source lines, locals or unchecked exception strings.
            frames = traceback.extract_tb(exc.__traceback__)[-16:]
            stack = "\n".join(
                f"  {Path(f.filename).name}:{f.lineno} in {f.name}" for f in frames
            )
            text += f"\n{stack}\n{type(exc).__name__}: {self._value('exception', self.redact(str(exc)))}"
        record = logging.LogRecord(
            "astrbot.plugin.astrbot_plugin_humanization",
            LEVELS[level],
            source[0],
            source[1],
            text[:8192],
            (),
            None,
            source[2],
        )
        record.levelname = level
        record.operation = self.trace.get()
        self._submit(record)
        if self.echo:
            # TRACK is a local severity, not an unsupported sixth host severity.
            echoed = logging.makeLogRecord(record.__dict__.copy())
            if record.operation:
                echoed.msg += f" [id={record.operation}]"
            if level == "TRACK":
                echoed.levelno, echoed.levelname = logging.DEBUG, "DEBUG"
                echoed.msg = "[TRACK] " + echoed.msg
            try:
                if self.console.isEnabledFor(echoed.levelno):
                    self.console.handle(echoed)
            except Exception as exc:
                self._emergency(exc)

    def _submit(self, record):
        if self.closed:
            return
        if (
            record.levelno >= logging.ERROR
            or not self.worker
            or not self.worker.is_alive()
        ):
            with self.lock:
                self._pending()
                self._write(record)
            return
        # Routine producers never wait for the file IO lock.
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            if record.levelno <= logging.DEBUG:
                self.dropped += 1
            else:
                with self.lock:
                    self._pending()
                    self._write(record)

    def _pending(self):
        # Called with the sink lock; preserve order before synchronous fallback.
        for _ in range(self.queue.qsize()):
            try:
                record = self.queue.get_nowait()
            except queue.Empty:
                return
            try:
                if record is not None:
                    self._write(record)
            finally:
                self.queue.task_done()

    def _write(self, record):
        with self.lock:
            try:
                if self.handler is None:
                    # Also works before async initialization or after writer failure.
                    self.directory.mkdir(parents=True, exist_ok=True)
                    with (self.directory / "humanization.log").open(
                        "a", encoding="utf-8", newline=""
                    ) as stream:
                        stream.write(
                            NativeFormatter(self.timezone)
                            .format(record)
                            .replace("\r\n", "\n")
                            .replace("\n", "\r\n")
                            + "\r\n"
                        )
                else:
                    self.handler.handle(record)
            except Exception as exc:
                self._emergency(exc, record)

    def _emergency(self, error, record=None):
        if not self.io_reported:
            self.io_reported = True
            try:
                sys.stderr.write(
                    f"Humanization log writer unavailable ({type(error).__name__})\n"
                    + (record.getMessage() + "\n" if record else "")
                )
                sys.stderr.flush()
            except Exception:
                pass

    def _write_loop(self):
        while True:
            with self.queue.not_empty:
                while not self.queue._qsize():
                    self.queue.not_empty.wait()
            with self.lock:
                try:
                    record = self.queue.get_nowait()
                except queue.Empty:
                    continue
                try:
                    if record is None:
                        return
                    self._write(record)
                finally:
                    self.queue.task_done()
                if self.dropped and self.queue.empty():
                    dropped, self.dropped = self.dropped, 0
                    self.warning("logging.dropped", records=dropped)

    async def flush(self):
        # A dead consumer must never leave queue.join() waiting forever.
        await asyncio.to_thread(self._drain)

    def _drain(self):
        while self.queue.unfinished_tasks:
            if self.worker and self.worker.is_alive():
                with self.queue.all_tasks_done:
                    if self.queue.unfinished_tasks:
                        self.queue.all_tasks_done.wait(timeout=0.1)
            else:
                try:
                    record = self.queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    if record is not None:
                        self._write(record)
                finally:
                    self.queue.task_done()
        if self.dropped:
            dropped, self.dropped = self.dropped, 0
            self.warning("logging.dropped", records=dropped)
            self._drain()

    async def clear(self, name="humanization.log"):
        """Clear the active file in queue order; archives remain untouched.

        Args:
            name: Only the active plugin log is allowed.

        Raises:
            ValueError: The filename is not the active log.
            RuntimeError: The writer has closed.
        """
        if name != "humanization.log":
            raise ValueError("Unknown plugin log")
        if self.closed:
            raise RuntimeError("Plugin log writer is closed")
        await self.flush()
        with self.lock:
            if self.handler and self.handler.stream:
                self.handler.stream.close()
                self.handler.stream = None
            (self.directory / name).write_bytes(b"")

    async def close(self):
        if self.tracker:
            self.tracker.close()
            self.tracker = None
        if self.closed:
            return
        if self.dropped:
            dropped, self.dropped = self.dropped, 0
            self.warning("logging.dropped", records=dropped)
        # Stop producers before draining; a cancelled unload still joins the worker.
        self.closed = True
        closing = asyncio.create_task(asyncio.to_thread(self._finish))
        try:
            await asyncio.shield(closing)
        except asyncio.CancelledError:
            await closing
            raise

    def _finish(self):
        self._drain()
        if self.worker and self.worker.is_alive():
            self.queue.put_nowait(None)
            self.worker.join()
        self.worker = None
        if self.handler:
            self.handler.close()
            self.handler = None
