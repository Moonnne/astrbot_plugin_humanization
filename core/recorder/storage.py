"""Bounded SQLite conversation storage with transactional summary cursors."""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import aiosqlite

from ..models import Message, ResetTarget
from .diary import DiaryProtocol


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
            CREATE TABLE IF NOT EXISTS diary_days (
                scope TEXT NOT NULL, day TEXT NOT NULL,
                through_seq INTEGER NOT NULL, created_at REAL NOT NULL,
                updated_at REAL NOT NULL, sealed INTEGER NOT NULL DEFAULT 0,
                coverage_gap INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(scope, day)
            );
            CREATE TABLE IF NOT EXISTS diary_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL, day TEXT NOT NULL,
                topic_at REAL NOT NULL, topic_time TEXT NOT NULL,
                topic TEXT NOT NULL, interact TEXT NOT NULL,
                reply TEXT NOT NULL, reaction TEXT NOT NULL,
                first_seq INTEGER NOT NULL, last_seq INTEGER NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL,
                FOREIGN KEY(scope, day) REFERENCES diary_days(scope, day) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS diary_topics_recent
                ON diary_topics(scope, day, updated_at DESC, id DESC);
            CREATE TABLE IF NOT EXISTS reply_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
                started_at REAL NOT NULL, trigger TEXT NOT NULL,
                status TEXT NOT NULL, sent_parts INTEGER NOT NULL DEFAULT 0,
                detail TEXT NOT NULL DEFAULT ''
            );
            PRAGMA user_version=2;
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

    async def diaries(
        self, scope: str, limit: int = 2, *, budget: int | None = None
    ) -> list[dict]:
        """Select complete topics and render days without mutating stored entries.

        Args:
            scope: Conversation identity.
            limit: Number of recent diary dates to read.
            budget: Shared topic character budget; None reads all selected topics.

        Returns:
            Chronological days with structured topics, readable body and omission counts.
        """
        days = await self.rows(
            "SELECT * FROM diary_days d WHERE scope=? AND (coverage_gap=1 OR EXISTS "
            "(SELECT 1 FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day)) "
            "ORDER BY day DESC LIMIT ?",
            (scope, limit),
        )
        for day in days:
            topics = await self.rows(
                "SELECT id,topic_at,topic_time,topic,interact,reply,reaction,first_seq,last_seq "
                "FROM diary_topics WHERE scope=? AND day=? ORDER BY updated_at DESC,id DESC",
                (scope, day["day"]),
            )
            selected = []
            for topic in topics:
                topic["interact"] = json.loads(topic["interact"])
                cost = max(
                    len(json.dumps(topic, ensure_ascii=False, separators=(",", ":"))),
                    len(DiaryProtocol.render_topic(topic)),
                )
                if budget is not None:
                    if cost > budget:
                        continue
                    budget -= cost
                selected.append(topic)
            selected.sort(key=lambda topic: (topic["topic_at"], topic["id"]))
            day["topics"] = selected
            day["omitted_topics"] = len(topics) - len(selected)
            parts = [f"# {day['day']}"]
            if day["coverage_gap"]:
                parts.append(
                    "[Coverage]覆盖缺口：部分原始消息已滚动淘汰或输入内容截断。"
                )
            if day["omitted_topics"]:
                parts.append(
                    f"[Context]另有 {day['omitted_topics']} 个话题未展示，不代表不存在。"
                )
            parts.extend(DiaryProtocol.render_topic(topic) for topic in selected)
            day["body"] = "\n\n".join(parts)
        return list(reversed(days))

    async def commit_summary(
        self,
        scope: str,
        day: str,
        changes: list[dict],
        through: int,
        human_count: int,
        now: float,
        *,
        coverage_gap: bool = False,
    ):
        """Commit validated topic changes and progress as one transaction.

        Args:
            scope: Conversation identity, also checked for every update.
            day: Writable diary date.
            changes: Validated topic additions or partial updates.
            through: Last processed sequence, including deliberately ignored messages.
            human_count: Corresponding incoming message counter.
            now: Commit timestamp.
            coverage_gap: Whether missing or clipped input was observed in this batch.
        """
        async with self.lock:
            sealed = await self.rows(
                "SELECT sealed FROM diary_days WHERE scope=? AND day=?", (scope, day)
            )
            if sealed and sealed[0]["sealed"]:
                raise ValueError("Cannot rewrite a sealed diary")
            try:
                await self.db.execute(
                    "UPDATE diary_days SET sealed=1 WHERE scope=? AND day<?",
                    (scope, day),
                )
                await self.db.execute(
                    "INSERT INTO diary_days(scope,day,through_seq,created_at,updated_at,coverage_gap) "
                    "VALUES(?,?,?,?,?,?) ON CONFLICT(scope,day) DO UPDATE SET "
                    "through_seq=excluded.through_seq,updated_at=excluded.updated_at,"
                    "coverage_gap=MAX(diary_days.coverage_gap,excluded.coverage_gap)",
                    (scope, day, through, now, now, coverage_gap),
                )
                for change in changes:
                    values = {
                        key: json.dumps(value, ensure_ascii=False)
                        if key == "interact"
                        else value
                        for key, value in change.items()
                        if key
                        in DiaryProtocol.fields
                        | {"first_seq", "last_seq", "topic_at", "topic_time"}
                    }
                    if change["action"] == "add":
                        values.update(
                            scope=scope, day=day, created_at=now, updated_at=now
                        )
                        columns = ",".join(values)
                        placeholders = ",".join(f":{key}" for key in values)
                        await self.db.execute(
                            f"INSERT INTO diary_topics({columns}) VALUES({placeholders})",
                            values,
                        )
                    else:
                        # A correction preserves the topic's first time and prior source extent.
                        first = values.pop("first_seq")
                        last = values.pop("last_seq")
                        values["updated_at"] = now
                        assignments = ",".join(f"{key}=?" for key in values)
                        result = await self.db.execute(
                            f"UPDATE diary_topics SET {assignments},first_seq=MIN(first_seq,?),"
                            "last_seq=MAX(last_seq,?) WHERE id=? AND scope=? AND day=?",
                            (*values.values(), first, last, change["id"], scope, day),
                        )
                        if result.rowcount != 1:
                            raise ValueError(
                                "Diary update target no longer exists in this day"
                            )
                await self.db.execute(
                    "UPDATE sessions SET cursor=?,summarized_count=? WHERE scope=?",
                    (through, human_count, scope),
                )
                await self.db.commit()
            except BaseException:
                await self.db.rollback()
                raise
        if self.log:
            self.log.debug(
                "database.summary.commit",
                scope=scope,
                day=day,
                changes=changes,
                through_seq=through,
            )

    async def update_session(self, scope: str, **values):
        allowed = {
            "cursor",
            "summarized_count",
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
                "UPDATE diary_days SET sealed=1 WHERE day<? AND sealed=0", (day,)
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

    async def reset(self, scope: str, day: str | None = None):
        """Reset one conversation, optionally retaining earlier diaries.

        Args:
            scope: Plugin conversation identity; never a global database reset.
            day: Diary date to remove, or None to remove all its diaries.
        """
        async with self.lock:
            try:
                await self.db.execute("DELETE FROM messages WHERE scope=?", (scope,))
                await self.db.execute("DELETE FROM reply_runs WHERE scope=?", (scope,))
                if day is None:
                    await self.db.execute(
                        "DELETE FROM diary_days WHERE scope=?", (scope,)
                    )
                else:
                    await self.db.execute(
                        "DELETE FROM diary_days WHERE scope=? AND day=?",
                        (scope, day),
                    )
                await self.db.execute("DELETE FROM sessions WHERE scope=?", (scope,))
                await self.db.commit()
            except BaseException:
                await self.db.rollback()
                raise

    async def reset_targets(self) -> list[ResetTarget]:
        """Locate current sessions and diary-only scopes retained by a today reset.

        Returns:
            Native routes and identities of every persisted plugin conversation.
        """
        targets = [
            ResetTarget(
                row["scope"],
                row["umo"],
                row["platform"],
                row["self_id"],
                row["group_id"],
                bool(row["private"]),
            )
            for row in await self.rows("SELECT * FROM sessions")
        ]
        for row in await self.rows(
            "SELECT DISTINCT scope FROM diary_days WHERE scope NOT IN (SELECT scope FROM sessions)"
        ):
            platform, self_id, kind, sid = json.loads(row["scope"])
            private = kind == "private"
            targets.append(
                ResetTarget(
                    row["scope"],
                    f"{platform}:{'FriendMessage' if private else 'GroupMessage'}:{sid}",
                    platform,
                    self_id,
                    "" if private else sid,
                    private,
                )
            )
        return targets

    async def reset_all(self):
        """Delete every plugin row atomically, keeping the database file and schema."""
        async with self.lock:
            try:
                for table in ("messages", "reply_runs", "diary_days", "sessions"):
                    await self.db.execute(f"DELETE FROM {table}")
                await self.db.commit()
            except BaseException:
                await self.db.rollback()
                raise
