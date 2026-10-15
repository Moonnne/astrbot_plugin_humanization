"""Own SQLite connections, transaction isolation and orderly checkpointing."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from .database_session import DatabaseSession
from .sql_queries import SqlQueries


class Database:
    """Serialize writes and lease two independent read-only connections.

    Transactions must contain database work only, never model or network calls.
    Closing rejects new leases and drains all accepted operations before checkpointing.
    """

    def __init__(self, path: Path, log=None):
        self.path = path
        self.log = log
        self.sql = SqlQueries()
        self._writer_lock = asyncio.Lock()
        self._condition = asyncio.Condition()
        self._readers = asyncio.Queue()
        self._connections = []
        self._active = 0
        self._state = "closed"
        self._close_task = None

    async def open(self):
        if self._state != "closed":
            raise RuntimeError("Database is already open")
        self._state = "opening"
        self._close_task = None
        try:
            await DatabaseSession.complete(self._open())
        except BaseException:
            await self.close()
            raise
        self._state = "open"

    async def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = await aiosqlite.connect(self.path, isolation_level=None)
        self._connections.append(self._writer)
        self._writer.row_factory = aiosqlite.Row
        async with self._writer.executescript(self.sql["connection.writer"]):
            pass
        async with self._writer.executescript(self.sql["schema.create"]):
            pass
        for _ in range(2):
            reader = await aiosqlite.connect(self.path, isolation_level=None)
            self._connections.append(reader)
            reader.row_factory = aiosqlite.Row
            async with reader.executescript(self.sql["connection.reader"]):
                pass
            self._readers.put_nowait(reader)

    @asynccontextmanager
    async def _lease(self):
        async with self._condition:
            if self._state != "open":
                raise RuntimeError("Database is not accepting operations")
            self._active += 1
        try:
            yield
        finally:
            async with self._condition:
                self._active -= 1
                self._condition.notify_all()

    @asynccontextmanager
    async def transaction(self):
        async with self._lease(), self._writer_lock:
            session = DatabaseSession(self._writer, self.log)
            try:
                await session.execute(self.sql["connection.begin_write"])
                yield session
                await DatabaseSession.complete(self._writer.commit())
            except BaseException:
                await DatabaseSession.complete(self._writer.rollback())
                raise

    @asynccontextmanager
    async def snapshot(self):
        async with self._lease():
            reader = await self._readers.get()
            session = DatabaseSession(reader, self.log)
            try:
                await session.execute(self.sql["connection.begin_read"])
                yield session
            finally:
                try:
                    await DatabaseSession.complete(reader.rollback())
                finally:
                    self._readers.put_nowait(reader)

    async def rows(self, sql: str, args=()) -> list[dict]:
        async with self.snapshot() as session:
            return await session.rows(sql, args)

    async def close(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        try:
            await asyncio.shield(self._close_task)
        except asyncio.CancelledError:
            await self._close_task
            raise

    async def _close(self):
        async with self._condition:
            self._state = "closing"
            self._condition.notify_all()
            await self._condition.wait_for(lambda: self._active == 0)
        try:
            # No plugin reader may retain a snapshot during the final checkpoint.
            for reader in self._connections[1:]:
                await reader.close()
            if self._connections:
                rows = await DatabaseSession(self._writer).rows(
                    self.sql["connection.checkpoint"]
                )
                if self.log:
                    self.log.info("database.checkpoint", **rows[0])
        except Exception:
            if self.log:
                self.log.exception("database.checkpoint.failed")
            raise
        finally:
            # Close even when checkpointing fails; never remove WAL/SHM manually.
            try:
                results = await asyncio.gather(
                    *(connection.close() for connection in self._connections),
                    return_exceptions=True,
                )
                for result in results:
                    if isinstance(result, BaseException):
                        raise result
            finally:
                self._connections.clear()
                self._readers = asyncio.Queue()
                self._state = "closed"
