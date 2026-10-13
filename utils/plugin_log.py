"""Mode-aware plugin logging with bounded runtime records and async file writes."""

import asyncio
import contextvars
import hashlib
import json
import logging
import re
import sys
import traceback
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path


class PluginLog:
    """Route core records to AstrBot or detailed records to the development file.

    Args:
        directory: Dedicated plugin log directory.
        debug: Whether all records go exclusively to dev.log.
        console: AstrBot-provided plugin logger; never reconfigured by this class.
        timezone: Configured timezone used for record timestamps.
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

    def __init__(self, directory: Path, debug: bool, console, timezone):
        self.directory = directory
        self.debug_mode = debug
        self.console = console
        self.timezone = timezone
        self.queue = asyncio.Queue()
        self.records = deque(maxlen=1000)
        self.trace = contextvars.ContextVar("humanization_log_trace", default="")
        self.worker = None
        self.closed = True
        self.io_reported = False

    async def open(self):
        def prepare():
            self.directory.mkdir(parents=True, exist_ok=True)
            runtime = self.directory / "runtime.log"
            dev = self.directory / "dev.log"
            runtime.touch(exist_ok=True)
            dev.touch(exist_ok=True)
            if not self.debug_mode:
                with runtime.open(encoding="utf-8") as stream:
                    self.records.extend(
                        line.rstrip("\r\n") for line in stream if line.strip()
                    )
                runtime.write_bytes(
                    "".join(line + "\r\n" for line in self.records).encode("utf-8")
                )

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

    def exception(self, event: str, **fields):
        error = sys.exc_info()[1]
        if error is not None:
            fields["error_type"] = type(error).__name__
            if self.debug_mode:
                fields["exception"] = "".join(traceback.format_exception(error))
        self._emit("ERROR", event, fields)

    def _emit(self, level: str, event: str, fields: dict):
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
        self.queue.put_nowait(json.dumps(record, ensure_ascii=False))
        if not self.debug_mode:
            self.console.log(
                getattr(logging, level),
                "Humanization %s %s",
                event,
                json.dumps(payload, ensure_ascii=False),
            )

    async def flush(self):
        if self.worker is not None:
            await self.queue.join()

    async def close(self):
        self.closed = True
        if self.worker is not None:
            self.queue.put_nowait(None)
            await self.worker
            self.worker = None
        self.records.clear()

    async def _write_loop(self):
        while True:
            first = await self.queue.get()
            batch = [first]
            while len(batch) < 128 and not self.queue.empty():
                batch.append(self.queue.get_nowait())
            lines = [line for line in batch if line is not None]
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
                for _ in batch:
                    self.queue.task_done()
            if None in batch:
                return

    def _write_batch(self, lines: list[str]):
        if self.debug_mode:
            with (self.directory / "dev.log").open("ab") as stream:
                stream.write("".join(line + "\r\n" for line in lines).encode("utf-8"))
        else:
            self.records.extend(lines)
            (self.directory / "runtime.log").write_bytes(
                "".join(line + "\r\n" for line in self.records).encode("utf-8")
            )
