"""Bounded SQLite conversation storage with transactional summary cursors."""

import asyncio
from dataclasses import asdict
from pathlib import Path

import aiosqlite

from ..models import Message


class Storage:
    def __init__(self, path: Path, retention: int, log=None):
        self.path = path
        self.retention = retention
        self.lock = asyncio.Lock()
        self.log = log

    async def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS sessions (
                scope TEXT PRIMARY KEY, umo TEXT NOT NULL, platform TEXT NOT NULL,
                self_id TEXT NOT NULL, group_id TEXT NOT NULL, private INTEGER NOT NULL,
                last_human REAL NOT NULL DEFAULT 0, last_reply REAL NOT NULL DEFAULT 0,
                cursor INTEGER NOT NULL DEFAULT 0, last_seq INTEGER NOT NULL DEFAULT 0,
                human_count INTEGER NOT NULL DEFAULT 0, summarized_count INTEGER NOT NULL DEFAULT 0,
                next_idle REAL NOT NULL DEFAULT 0, idle_waiting INTEGER NOT NULL DEFAULT 0,
                idle_day TEXT NOT NULL DEFAULT '', idle_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
                seq INTEGER NOT NULL, human_count INTEGER NOT NULL,
                umo TEXT NOT NULL, platform TEXT NOT NULL, self_id TEXT NOT NULL,
                group_id TEXT NOT NULL, sender_id TEXT NOT NULL, sender_name TEXT NOT NULL,
                message_id TEXT NOT NULL, sent_at REAL NOT NULL, received_at REAL NOT NULL,
                text TEXT NOT NULL, segments TEXT NOT NULL, private INTEGER NOT NULL,
                day TEXT NOT NULL, direction TEXT NOT NULL,
                FOREIGN KEY(scope) REFERENCES sessions(scope)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS messages_source ON messages(scope, direction, message_id)
                WHERE message_id != '';
            CREATE INDEX IF NOT EXISTS messages_recent ON messages(scope, seq);
            CREATE TABLE IF NOT EXISTS daily_summaries (
                scope TEXT NOT NULL, day TEXT NOT NULL, body TEXT NOT NULL,
                through_seq INTEGER NOT NULL, updated_at REAL NOT NULL,
                sealed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(scope, day)
            );
            CREATE TABLE IF NOT EXISTS reply_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
                started_at REAL NOT NULL, trigger TEXT NOT NULL,
                status TEXT NOT NULL, sent_parts INTEGER NOT NULL DEFAULT 0,
                detail TEXT NOT NULL DEFAULT ''
            );
            PRAGMA user_version=1;
        """)
        # Interrupted sends are not retried: the remote side may already have accepted them.
        await self.db.execute(
            "UPDATE reply_runs SET status='unknown' WHERE status='generating'"
        )
        await self.trim()

    async def close(self):
        await self.db.close()

    async def rows(self, query: str, args=()) -> list[dict]:
        async with self.db.execute(query, args) as cursor:
            result = [dict(row) for row in await cursor.fetchall()]
        if self.log:
            self.log.debug(
                "database.query", query=query, parameters=args, result=result
            )
        return result

    async def session(self, scope: str) -> dict:
        return (await self.rows("SELECT * FROM sessions WHERE scope=?", (scope,)))[0]

    async def trim(self):
        async with self.lock:
            for row in await self.rows("SELECT scope FROM sessions"):
                await self.db.execute(
                    "DELETE FROM messages WHERE scope=? AND id NOT IN "
                    "(SELECT id FROM messages WHERE scope=? ORDER BY seq DESC LIMIT ?)",
                    (row["scope"], row["scope"], self.retention),
                )
            await self.db.execute(
                "DELETE FROM reply_runs WHERE id NOT IN (SELECT id FROM reply_runs ORDER BY id DESC LIMIT 1000)"
            )
            await self.db.commit()

    async def append(self, message: Message) -> bool:
        """Insert once and trim atomically; only incoming messages advance activity.

        Args:
            message: Normalized received message or successfully sent bubble.

        Returns:
            False for an adapter duplicate, True for a newly inserted record.
        """
        async with self.lock:
            if message.message_id and await self.rows(
                "SELECT id FROM messages WHERE scope=? AND direction=? AND message_id=?",
                (message.scope, message.direction, message.message_id),
            ):
                return False
            data = asdict(message)
            try:
                await self.db.execute(
                    "INSERT INTO sessions(scope,umo,platform,self_id,group_id,private) "
                    "VALUES(:scope,:umo,:platform,:self_id,:group_id,:private) ON CONFLICT(scope) DO NOTHING",
                    data,
                )
                incoming = message.direction == "in"
                await self.db.execute(
                    "UPDATE sessions SET last_seq=last_seq+1,human_count=human_count+?,"
                    "last_human=CASE WHEN ? THEN ? ELSE last_human END,"
                    "idle_waiting=CASE WHEN ? THEN 0 ELSE idle_waiting END,"
                    "umo=CASE WHEN ? THEN ? ELSE umo END WHERE scope=?",
                    (
                        incoming,
                        incoming,
                        message.received_at,
                        incoming,
                        incoming,
                        message.umo,
                        message.scope,
                    ),
                )
                session = await self.session(message.scope)
                data.update(seq=session["last_seq"], human_count=session["human_count"])
                columns = ",".join(data)
                placeholders = ",".join(f":{name}" for name in data)
                await self.db.execute(
                    f"INSERT INTO messages({columns}) VALUES({placeholders})", data
                )
                await self.db.execute(
                    "DELETE FROM messages WHERE scope=? AND seq<=?",
                    (message.scope, session["last_seq"] - self.retention),
                )
                await self.db.commit()
                if self.log:
                    self.log.debug(
                        "database.message.append", record=data, retention=self.retention
                    )
            except BaseException:
                await self.db.rollback()
                raise
        return True

    async def recent(self, scope: str, limit: int) -> list[dict]:
        rows = await self.rows(
            "SELECT * FROM messages WHERE scope=? ORDER BY seq DESC LIMIT ?",
            (scope, limit),
        )
        return list(reversed(rows))

    async def diaries(self, scope: str, limit: int = 2) -> list[dict]:
        rows = await self.rows(
            "SELECT * FROM daily_summaries WHERE scope=? ORDER BY day DESC LIMIT ?",
            (scope, limit),
        )
        return list(reversed(rows))

    async def commit_summary(
        self,
        scope: str,
        day: str,
        body: str,
        through: int,
        human_count: int,
        now: float,
    ):
        async with self.lock:
            sealed = await self.rows(
                "SELECT sealed FROM daily_summaries WHERE scope=? AND day=?",
                (scope, day),
            )
            if sealed and sealed[0]["sealed"]:
                raise ValueError("Cannot rewrite a sealed diary")
            try:
                await self.db.execute(
                    "UPDATE daily_summaries SET sealed=1 WHERE scope=? AND day<?",
                    (scope, day),
                )
                await self.db.execute(
                    "INSERT INTO daily_summaries VALUES(?,?,?,?,?,0) ON CONFLICT(scope,day) DO UPDATE SET "
                    "body=excluded.body,through_seq=excluded.through_seq,updated_at=excluded.updated_at "
                    "WHERE daily_summaries.sealed=0",
                    (scope, day, body, through, now),
                )
                await self.db.execute(
                    "UPDATE sessions SET cursor=?,summarized_count=? WHERE scope=?",
                    (through, human_count, scope),
                )
                await self.db.commit()
                if self.log:
                    self.log.debug(
                        "database.summary.commit",
                        scope=scope,
                        day=day,
                        through_seq=through,
                        body=body,
                    )
            except BaseException:
                await self.db.rollback()
                raise

    async def update_session(self, scope: str, **values):
        allowed = {
            "last_human",
            "last_reply",
            "next_idle",
            "idle_waiting",
            "idle_day",
            "idle_count",
        }
        if not values.keys() <= allowed:
            raise ValueError("Unsupported session state field")
        async with self.lock:
            await self.db.execute(
                "UPDATE sessions SET "
                + ",".join(f"{key}=?" for key in values)
                + " WHERE scope=?",
                (*values.values(), scope),
            )
            await self.db.commit()

    async def seal_before(self, day: str):
        async with self.lock:
            await self.db.execute(
                "UPDATE daily_summaries SET sealed=1 WHERE day<? AND sealed=0", (day,)
            )
            await self.db.commit()

    async def record_reply_activity(
        self, scope: str, now: float, day: str, idle_human: float | None
    ):
        """Update delivery activity without overwriting a concurrent human response.

        Args:
            scope: Shared conversation identity.
            now: Native sending-stage completion timestamp.
            day: Local calendar date for the daily proactive count.
            idle_human: Human activity timestamp captured by the idle trigger,
                supplied only for the first proactive bubble that completes sending.
        """
        async with self.lock:
            await self.db.execute(
                "UPDATE sessions SET last_reply=? WHERE scope=?", (now, scope)
            )
            if idle_human is not None:
                await self.db.execute(
                    "UPDATE sessions SET idle_waiting=CASE WHEN last_human=? THEN 1 ELSE 0 END,"
                    "idle_count=CASE WHEN idle_day=? THEN idle_count+1 ELSE 1 END,idle_day=? WHERE scope=?",
                    (idle_human, day, day, scope),
                )
            await self.db.commit()

    async def start_reply(self, scope: str, now: float, trigger: str) -> int:
        async with self.lock:
            cursor = await self.db.execute(
                "INSERT INTO reply_runs(scope,started_at,trigger,status) VALUES(?,?,?,'generating')",
                (scope, now, trigger),
            )
            await self.db.execute(
                "DELETE FROM reply_runs WHERE id NOT IN (SELECT id FROM reply_runs ORDER BY id DESC LIMIT 1000)"
            )
            await self.db.commit()
            return cursor.lastrowid

    async def finish_reply(
        self, run: int, status: str, sent: int = 0, detail: str = ""
    ):
        async with self.lock:
            await self.db.execute(
                "UPDATE reply_runs SET status=?,sent_parts=?,detail=? WHERE id=?",
                (status, sent, detail, run),
            )
            await self.db.commit()
