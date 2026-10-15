"""Bounded SQLite conversation storage with transactional summary cursors."""

import json
from dataclasses import asdict
from pathlib import Path

from ...models.message import Message
from ...models.session import ResetTarget
from ...utils.database import Database
from .diary import DiaryProtocol


class Storage:
    def __init__(self, path: Path, retention: int, log=None):
        self.path = path
        self.retention = retention
        self.log = log
        self.database = Database(path, log)
        self.sql = self.database.sql

    async def open(self):
        await self.database.open()
        try:
            async with self.database.transaction() as tx:
                await tx.execute(self.sql["reply_runs.open_update"])
                await tx.execute(self.sql["controller_decisions.open_update"])
            await self.trim()
        except BaseException:
            await self.database.close()
            raise

    async def close(self):
        await self.database.close()

    async def rows(self, query: str, args=()) -> list[dict]:
        return await self.database.rows(query, args)

    async def session(self, scope: str) -> dict:
        return (await self.rows(self.sql["sessions.session_select"], (scope,)))[0]

    async def trim(self):
        async with self.database.transaction() as tx:
            for row in await tx.rows(self.sql["sessions.trim_select"]):
                await tx.execute(
                    self.sql["messages.trim_delete"],
                    (row["scope"], row["scope"], self.retention),
                )
            await tx.execute(self.sql["reply_runs.trim_delete"])

    async def append(self, message: Message) -> bool:
        """Insert once and trim atomically; only incoming messages advance activity.

        Args:
            message: Normalized received message or successfully sent bubble.

        Returns:
            False for an adapter duplicate, True for a newly inserted record.
        """
        async with self.database.transaction() as tx:
            if message.message_id and await tx.rows(
                self.sql["messages.append_select"],
                (message.scope, message.direction, message.message_id),
            ):
                return False
            data = asdict(message)
            await tx.execute(
                self.sql["sessions.append_insert"],
                data,
            )
            incoming = message.direction == "in"
            await tx.execute(
                self.sql["sessions.append_update"],
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
            session = (
                await tx.rows(self.sql["sessions.session_select"], (message.scope,))
            )[0]
            data.update(seq=session["last_seq"], human_count=session["human_count"])
            await tx.execute(self.sql["messages.append_insert"], data)
            await tx.execute(
                self.sql["messages.append_delete"],
                (message.scope, session["last_seq"] - self.retention),
            )
        if self.log:
            self.log.debug(
                "database.message.append", record=data, retention=self.retention
            )
        return True

    async def recent(self, scope: str, limit: int) -> list[dict]:
        rows = await self.rows(
            self.sql["messages.recent_select"],
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
        async with self.database.snapshot() as tx:
            days = await tx.rows(
                self.sql["diary_days.diaries_select"],
                (scope, limit),
            )
            for day in days:
                topics = await tx.rows(
                    self.sql["diary_topics.diaries_select"],
                    (scope, day["day"]),
                )
                selected = []
                for topic in topics:
                    topic["interact"] = json.loads(topic["interact"])
                    cost = max(
                        len(
                            json.dumps(topic, ensure_ascii=False, separators=(",", ":"))
                        ),
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

    async def controller_topics(self, scope: str, count: int, budget: int) -> dict:
        """Read recent complete topics across dates under the planner's own budget.

        Args:
            scope: Canonical conversation identity.
            count: Maximum candidate count; zero disables topic observation.
            budget: Character budget for serialized complete topic records.

        Returns:
            Chronological items and explicit candidate/included/omitted counts.
        """
        candidates = await self.rows(
            self.sql["diary_topics.controller_topics_select"],
            (scope, count),
        )
        items = []
        for topic in candidates:
            topic["interact"] = json.loads(topic["interact"])
            cost = len(json.dumps(topic, ensure_ascii=False, separators=(",", ":")))
            if cost > budget:
                continue
            budget -= cost
            items.append(topic)
        items.sort(key=lambda topic: (topic["topic_at"], topic["id"]))
        return {
            "items": items,
            "candidate_count": len(candidates),
            "included_count": len(items),
            "omitted_count": len(candidates) - len(items),
        }

    async def decisions(self, scope: str) -> list[dict]:
        rows = await self.rows(
            self.sql["controller_decisions.decisions_select"],
            (scope,),
        )
        for row in rows:
            row["decision"] = json.loads(row.pop("decision_json"))
        return list(reversed(rows))

    async def record_decision(
        self, scope, data, now, through, last_human, trigger, required
    ):
        """Persist a validated decision and trim only this conversation atomically.

        Args:
            scope: Canonical conversation identity.
            data: Validated Controller output.
            now: Actual assessment completion timestamp.
            through: Observed message sequence watermark.
            last_human: Last human arrival timestamp known at assessment start.
            trigger: Message or idle evaluation.
            required: Whether reply was required by a configured direct trigger.

        Returns:
            The inserted decision ID for later execution-result updates.
        """
        async with self.database.transaction() as tx:
            result = await tx.execute(
                self.sql["controller_decisions.record_decision_insert"],
                (
                    scope,
                    now,
                    through,
                    last_human,
                    trigger,
                    required,
                    json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                    "pending" if data["reply"] else "observed",
                ),
            )
            await tx.execute(
                self.sql["controller_decisions.record_decision_delete"],
                (scope, scope),
            )
            return result.lastrowid

    async def finish_decision(self, decision_id: int, outcome: str):
        async with self.database.transaction() as tx:
            await tx.execute(
                self.sql["controller_decisions.finish_decision_update"],
                (outcome, decision_id),
            )

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
        async with self.database.transaction() as tx:
            sealed = await tx.rows(
                self.sql["diary_days.commit_summary_select"], (scope, day)
            )
            if sealed and sealed[0]["sealed"]:
                raise ValueError("Cannot rewrite a sealed diary")
            await tx.execute(
                self.sql["diary_days.commit_summary_update"],
                (scope, day),
            )
            await tx.execute(
                self.sql["diary_days.commit_summary_insert"],
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
                    values.update(scope=scope, day=day, created_at=now, updated_at=now)
                    await tx.execute(
                        self.sql["diary_topics.commit_summary_insert"],
                        values,
                    )
                else:
                    # A correction preserves the topic's first time and prior source extent.
                    first = values.pop("first_seq")
                    last = values.pop("last_seq")
                    values["updated_at"] = now
                    result = await tx.execute(
                        self.sql["diary_topics.commit_summary_update"],
                        {
                            **dict.fromkeys(DiaryProtocol.fields),
                            **values,
                            "first_seq": first,
                            "last_seq": last,
                            "id": change["id"],
                            "scope": scope,
                            "day": day,
                        },
                    )
                    if result.rowcount != 1:
                        raise ValueError(
                            "Diary update target no longer exists in this day"
                        )
            await tx.execute(
                self.sql["sessions.commit_summary_update"],
                (through, human_count, scope),
            )
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
        async with self.database.transaction() as tx:
            await tx.execute(
                self.sql["sessions.update_session_update"],
                {
                    **dict.fromkeys(allowed),
                    **values,
                    **{f"set_{key}": key in values for key in allowed},
                    "scope": scope,
                },
            )

    async def seal_before(self, day: str):
        async with self.database.transaction() as tx:
            await tx.execute(self.sql["diary_days.seal_before_update"], (day,))

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
        async with self.database.transaction() as tx:
            await tx.execute(
                self.sql["sessions.record_reply_activity_update"], (now, scope)
            )
            if idle_human is not None:
                await tx.execute(
                    self.sql["sessions.record_reply_activity_update_2"],
                    (idle_human, day, day, scope),
                )

    async def start_reply(self, scope: str, now: float, trigger: str) -> int:
        async with self.database.transaction() as tx:
            cursor = await tx.execute(
                self.sql["reply_runs.start_reply_insert"],
                (scope, now, trigger),
            )
            await tx.execute(self.sql["reply_runs.trim_delete"])
            return cursor.lastrowid

    async def finish_reply(
        self, run: int, status: str, sent: int = 0, detail: str = ""
    ):
        async with self.database.transaction() as tx:
            await tx.execute(
                self.sql["reply_runs.finish_reply_update"],
                (status, sent, detail, run),
            )

    async def reset(self, scope: str, day: str | None = None):
        """Reset one conversation, optionally retaining earlier diaries.

        Args:
            scope: Plugin conversation identity; never a global database reset.
            day: Diary date to remove, or None to remove all its diaries.
        """
        async with self.database.transaction() as tx:
            await tx.execute(self.sql["messages.reset_delete"], (scope,))
            await tx.execute(self.sql["reply_runs.reset_delete"], (scope,))
            await tx.execute(self.sql["controller_decisions.reset_delete"], (scope,))
            if day is None:
                await tx.execute(self.sql["diary_days.reset_delete"], (scope,))
            else:
                await tx.execute(
                    self.sql["diary_days.reset_delete_2"],
                    (scope, day),
                )
            await tx.execute(self.sql["sessions.reset_delete"], (scope,))

    async def reset_targets(self) -> list[ResetTarget]:
        """Locate current sessions and diary-only scopes retained by a today reset.

        Returns:
            Native routes and identities of every persisted plugin conversation.
        """
        async with self.database.snapshot() as tx:
            targets = [
                ResetTarget(
                    row["scope"],
                    row["umo"],
                    row["platform"],
                    row["self_id"],
                    row["group_id"],
                    bool(row["private"]),
                )
                for row in await tx.rows(self.sql["sessions.reset_targets_select"])
            ]
            for row in await tx.rows(self.sql["diary_days.reset_targets_select"]):
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
        """Delete every plugin row atomically, retaining the file and schema."""
        async with self.database.transaction() as tx:
            await tx.execute(self.sql["messages.reset_all_delete"])
            await tx.execute(self.sql["reply_runs.reset_all_delete"])
            await tx.execute(self.sql["diary_days.reset_all_delete"])
            await tx.execute(self.sql["controller_decisions.reset_all_delete"])
            await tx.execute(self.sql["sessions.reset_all_delete"])

    async def message_count(self, scope, through_seq=None):
        rows = await self.rows(
            self.sql["messages.message_count_select"],
            (scope, through_seq, through_seq),
        )
        return rows[0]["count"]

    async def pending_sessions(self):
        return await self.rows(self.sql["sessions.pending_sessions_select"])

    async def group_sessions(self):
        return await self.rows(self.sql["sessions.group_sessions_select"])

    async def pending_messages(self, scope, cursor, limit):
        return await self.rows(
            self.sql["messages.pending_messages_select"],
            (scope, cursor, limit),
        )

    async def preceding_messages(self, scope, through, limit):
        return await self.rows(
            self.sql["messages.preceding_messages_select"],
            (scope, through, limit),
        )

    async def info(self, scope):
        async with self.database.snapshot() as tx:
            counts = await tx.rows(
                self.sql["messages.info_select"],
                (scope, scope, scope),
            )
            diary = await tx.rows(
                self.sql["diary_days.info_select"],
                (scope,),
            )
        return counts[0], diary
