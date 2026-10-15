"""Short-lived SQLite operations with deterministic cursor cleanup."""

import asyncio

from ..models.database import WriteResult


class DatabaseSession:
    def __init__(self, connection, log=None):
        self._connection = connection
        self.log = log

    @staticmethod
    async def complete(operation):
        """Finish queued SQLite work before propagating cancellation."""
        task = asyncio.create_task(operation)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise

    async def rows(self, sql: str, args=()) -> list[dict]:
        async def fetch():
            async with self._connection.execute(sql, args) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

        rows = await self.complete(fetch())
        if self.log:
            self.log.debug("database.query", query=sql, parameters=args, result=rows)
        return rows

    async def execute(self, sql: str, args=()) -> WriteResult:
        async def run():
            async with self._connection.execute(sql, args) as cursor:
                return WriteResult(cursor.lastrowid, cursor.rowcount)

        return await self.complete(run())
