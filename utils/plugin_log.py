"""Mode-aware plugin logging with byte limits and asynchronous file writes."""

import asyncio
import contextvars
import hashlib
import json
import logging
import re
import sys
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path


class PluginLog:
    """Route core records to AstrBot or detailed records to the development file.

    Args:
        directory: Dedicated plugin log directory.
        debug: Whether detailed records go to dev.log instead of the console.
        console: AstrBot-provided plugin logger; never reconfigured by this class.
        timezone: Configured timezone used for record timestamps.
        runtime_max_mb: Runtime file limit in MiB; zero disables rolling.
        dev_max_mb: Development file limit in MiB; zero disables rolling.
    """

    _credential_key = re.compile(
        r"(?:^key$|api[_-]?key|access[_-]?key|private[_-]?key|token|jwt|password|passwd|secret|authorization|cookie|credential|密钥|令牌|密码)",
        re.I,
    )
    _credential_text = re.compile(
        r"(?i)(\b(?:api[_-]?key|access[_-]?key|private[_-]?key|key|access[_-]?token|token|jwt|password|passwd|secret|authorization|cookie|credential|密钥|令牌|密码)\b[\"']?\s*[:=]\s*[\"']?)([^\s\"',;}]+)"
    )
    _bearer = re.compile(r"(?i)\bBearer\s+[^\s\"',;}]+")
    _key_token = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
    _binary_key = re.compile(
        r"(?:base64|binary|image_data|audio_data|video_data)$", re.I
    )
    _data_uri = re.compile(r"data:[^\s;,]+;base64,[A-Za-z0-9+/=]+", re.I)

    def __init__(
        self,
        directory: Path,
        debug: bool,
        console,
        timezone,
        runtime_max_mb: float = 5,
        dev_max_mb: float = 10,
    ):
        self.directory = directory
        self.debug_mode = debug
        self.console = console
        self.timezone = timezone
        self.queue = asyncio.Queue()
        self.limits = {
            name: max(1, int(size * 1024 * 1024)) if size else 0
            for name, size in (
                ("runtime.log", runtime_max_mb),
                ("dev.log", dev_max_mb),
            )
        }
        self.trace = contextvars.ContextVar("humanization_log_trace", default="")
        self.worker = None
        self.closed = True
        self.io_reported = False

    async def open(self):
        def prepare():
            self.directory.mkdir(parents=True, exist_ok=True)
            for name in self.limits:
                (self.directory / name).touch(exist_ok=True)
                self._trim_file(name)

        try:
            await asyncio.to_thread(prepare)
        except OSError as exc:
            self.console.error(
                "Humanization log files unavailable (%s)", type(exc).__name__
            )
            self.io_reported = True
        self.closed = False
        self.worker = asyncio.create_task(
            self._write_loop(), name="humanization-log-writer"
        )

    @asynccontextmanager
    async def context(self, prefix: str):
        """Correlate nested model and hook records within one async task.

        Args:
            prefix: Operation category used in the generated correlation ID.
        """
        token = self.trace.set(f"{prefix}-{uuid.uuid4().hex[:12]}")
        try:
            yield
        finally:
            try:
                self.trace.reset(token)
            except ValueError:
                # Async-generator finalization can run in a different task/context.
                self.trace.set("")

    @staticmethod
    def identity(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def redact(cls, value):
        """Mask credentials in structured payloads and textual model/tool results.

        Args:
            value: JSON-like diagnostic data, never an entire provider configuration.

        Returns:
            Serializable payload with credential values and binary bodies removed.
        """
        if isinstance(value, dict):
            return {
                str(key): "[REDACTED]"
                if cls._credential_key.search(str(key))
                else {"binary_chars": len(item)}
                if cls._binary_key.search(str(key)) and isinstance(item, (str, bytes))
                else cls.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls.redact(item) for item in value]
        if isinstance(value, bytes):
            return {"binary_bytes": len(value)}
        if isinstance(value, str):
            value = cls._data_uri.sub("[BINARY DATA OMITTED]", value)
            value = cls._bearer.sub("Bearer [REDACTED]", value)
            value = cls._key_token.sub("[REDACTED]", value)
            return cls._credential_text.sub(r"\1[REDACTED]", value)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return {"object_type": type(value).__name__}

    def info(self, event: str, **fields):
        self._emit("INFO", event, fields)

    def debug(self, event: str, **details):
        if self.debug_mode:
            self._emit("DEBUG", event, details)

    def model_usage(self, **fields):
        """Persist model counters in runtime.log without console output.

        Args:
            **fields: Counters and call metadata, excluding prompts and responses.
        """
        self._emit("INFO", "model.usage", fields, runtime_only=True)

    def exception(self, event: str, **fields):
        error = sys.exc_info()[1]
        if error is not None:
            fields["error_type"] = type(error).__name__
            if self.debug_mode:
                fields["exception"] = "".join(traceback.format_exception(error))
        self._emit("ERROR", event, fields)

    def _emit(self, level: str, event: str, fields: dict, runtime_only: bool = False):
        if self.closed:
            return
        payload = self.redact(fields)
        record = {
            "time": datetime.now(self.timezone).isoformat(timespec="milliseconds"),
            "level": level,
            "event": event,
            "trace": self.trace.get(),
            "data": payload,
        }
        names = ["dev.log"] if self.debug_mode else ["runtime.log"]
        if runtime_only and "runtime.log" not in names:
            names.append("runtime.log")
        line = json.dumps(record, ensure_ascii=False)
        self.queue.put_nowait(dict.fromkeys(names, line))
        if not self.debug_mode and not runtime_only:
            self.console.log(
                getattr(logging, level),
                "Humanization %s %s",
                event,
                json.dumps(payload, ensure_ascii=False),
            )

    async def flush(self):
        if self.worker is not None:
            await self.queue.join()

    async def clear(self, name: str):
        """Truncate one log in queue order, after all earlier writes finish.

        Args:
            name: Either runtime.log or dev.log.

        Raises:
            ValueError: The requested file is not a plugin log.
            RuntimeError: The writer has already closed.
            OSError: The selected log cannot be truncated.
        """
        if name not in ("runtime.log", "dev.log"):
            raise ValueError("Unknown plugin log")
        if self.closed:
            raise RuntimeError("Plugin log writer is closed")
        completed = asyncio.get_running_loop().create_future()
        self.queue.put_nowait((name, completed))
        await asyncio.shield(completed)

    async def close(self):
        self.closed = True
        if self.worker is not None:
            self.queue.put_nowait(None)
            await self.worker
            self.worker = None

    async def _write_loop(self):
        while True:
            first = await self.queue.get()
            batch = [first]
            while (
                isinstance(batch[-1], dict)
                and len(batch) < 128
                and not self.queue.empty()
            ):
                batch.append(self.queue.get_nowait())
            lines = [line for line in batch if isinstance(line, dict)]
            try:
                if lines:
                    await asyncio.to_thread(self._write_batch, lines)
            except OSError as exc:
                if not self.io_reported:
                    self.console.error(
                        "Humanization log writer failed (%s)", type(exc).__name__
                    )
                    self.io_reported = True
            finally:
                for _ in lines:
                    self.queue.task_done()
            last = batch[-1]
            if isinstance(last, tuple):
                name, completed = last
                try:
                    await asyncio.to_thread((self.directory / name).write_bytes, b"")
                except OSError as exc:
                    completed.set_exception(exc)
                else:
                    completed.set_result(None)
                finally:
                    self.queue.task_done()
            elif last is None:
                self.queue.task_done()
                return

    def _write_batch(self, lines: list[dict[str, str]]):
        for name, limit in self.limits.items():
            records = [
                (line[name] + "\r\n").encode("utf-8") for line in lines if name in line
            ]
            # A single oversized JSON record cannot fit as a complete line.
            data = b"".join(
                record for record in records if not limit or len(record) <= limit
            )
            if data:
                with (self.directory / name).open("ab") as stream:
                    stream.write(data)
                self._trim_file(name)

    def _trim_file(self, name: str):
        """Keep the newest complete lines within the file's byte budget.

        Args:
            name: One of the two fixed plugin log filenames.
        """
        limit = self.limits[name]
        path = self.directory / name
        size = path.stat().st_size
        if not limit or size <= limit:
            return
        with path.open("rb") as stream:
            stream.seek(size - limit - 1)
            boundary = stream.read(1) == b"\n"
            data = stream.read()
        if not boundary:
            data = data.partition(b"\n")[2]
        path.write_bytes(data)
