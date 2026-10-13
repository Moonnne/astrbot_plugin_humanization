"""Incremental summaries with bounded input and retryable cursors."""

import asyncio
import json
from datetime import datetime


class Summarizer:
    def __init__(self, storage, settings, generate, prompt: str, log):
        self.storage = storage
        self.settings = settings
        self.generate = generate
        self.prompt = prompt
        self.log = log
        self.lock = asyncio.Lock()

    async def tick(self):
        today = datetime.now(self.settings.timezone).date().isoformat()
        await self.storage.seal_before(today)
        if not self.settings.recorder["summary_provider"]:
            return
        async with self.lock:
            for session in await self.storage.rows(
                "SELECT * FROM sessions WHERE last_seq>cursor"
            ):
                group_umo = f"{session['platform']}:GroupMessage:{session['group_id']}"
                if not self.settings.selected(session["umo"], group_umo):
                    continue
                pending = await self.storage.rows(
                    "SELECT * FROM messages WHERE scope=? AND seq>? ORDER BY seq LIMIT ?",
                    (
                        session["scope"],
                        session["cursor"],
                        self.settings.recorder["window"],
                    ),
                )
                if not pending:
                    continue
                if (
                    session["human_count"] - session["summarized_count"]
                    < self.settings.recorder["summary_every"]
                    and pending[0]["day"] == today
                ):
                    continue
                async with self.log.context("summary"):
                    try:
                        await self.summarize(session, pending)
                    except Exception:
                        self.log.exception("summary.failed", cursor=session["cursor"])

    async def summarize(self, session: dict, pending: list[dict]):
        """Advance only over the rows actually included in the model request.

        Args:
            session: Persisted cursor and message counters.
            pending: Earliest retained messages after the cursor.
        """
        config = self.settings.recorder
        self.log.info(
            "summary.start",
            conversation=self.log.identity(session["scope"]),
            pending_count=len(pending),
            cursor=session["cursor"],
        )
        selected = []
        size = 0
        for row in pending:
            item = {
                key: row[key]
                for key in (
                    "seq",
                    "sent_at",
                    "day",
                    "sender_id",
                    "sender_name",
                    "direction",
                    "text",
                )
            }
            # Clip an individual oversized message explicitly; never imply full coverage.
            if len(item["text"]) > config["context_chars"] // 2:
                item["text"] = (
                    item["text"][: config["context_chars"] // 2] + "[内容截断]"
                )
            cost = len(json.dumps(item, ensure_ascii=False))
            if selected and size + cost > config["context_chars"]:
                break
            selected.append(item)
            size += cost
        now = datetime.now(self.settings.timezone)
        day = now.date().isoformat()
        diaries = await self.storage.diaries(session["scope"])
        gap = pending[0]["seq"] > session["cursor"] + 1
        # Overlap supplies context without advancing already summarized messages.
        overlap = []
        if len(selected) < config["window"] and size < config["context_chars"]:
            preceding = await self.storage.rows(
                "SELECT * FROM messages WHERE scope=? AND seq<=? ORDER BY seq DESC LIMIT ?",
                (session["scope"], session["cursor"], config["window"] - len(selected)),
            )
            for row in preceding:
                item = {
                    key: row[key]
                    for key in (
                        "seq",
                        "sent_at",
                        "day",
                        "sender_id",
                        "sender_name",
                        "direction",
                        "text",
                    )
                }
                cost = len(json.dumps(item, ensure_ascii=False))
                if size + cost > config["context_chars"]:
                    break
                overlap.append(item)
                size += cost
        payload = {
            "date": day,
            "existing_diaries": diaries,
            "messages": selected,
            "overlap_for_context_only": list(reversed(overlap)),
            "coverage_gap": gap,
            "instruction": "合并为今日完整日记；旧日期消息作为补记，历史日记仅供参考。",
        }
        self.log.debug(
            "summary.input", provider=config["summary_provider"], payload=payload
        )
        async with asyncio.timeout(config["summary_timeout"]):
            body = await self.generate(
                config["summary_provider"],
                self.prompt,
                json.dumps(payload, ensure_ascii=False),
            )
        body = body.strip()
        if not body:
            raise ValueError("Summary model returned empty text")
        if datetime.now(self.settings.timezone).date().isoformat() != day:
            raise ValueError(
                "Diary date changed during generation; retry on the new day"
            )
        body = body[: config["summary_chars"]]
        if gap:
            body = "[覆盖缺口：部分原始消息已滚动淘汰]\n" + body
        through = selected[-1]["seq"]
        count = next(row["human_count"] for row in pending if row["seq"] == through)
        await self.storage.commit_summary(
            session["scope"], day, body, through, count, now.timestamp()
        )
        self.log.debug(
            "summary.output", body=body, through_seq=through, human_count=count
        )
        self.log.info(
            "summary.complete",
            through_seq=through,
            message_count=len(selected),
            diary_chars=len(body),
            coverage_gap=gap,
        )
