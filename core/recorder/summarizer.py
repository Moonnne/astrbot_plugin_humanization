"""Incremental summaries with bounded input and retryable cursors."""

import asyncio
import json
from datetime import datetime
from time import perf_counter

from .diary import DiaryProtocol


class Summarizer:
    def __init__(
        self, storage, settings, generate, prompt: str, log, robot_record_filter=None
    ):
        self.storage = storage
        self.settings = settings
        self.generate = generate
        self.prompt = prompt
        self.log = log
        self.robot_record_filter = robot_record_filter
        self.lock = asyncio.Lock()
        self.active_scope = None
        self.resetting = set()

    async def tick(self):
        today = datetime.now(self.settings.timezone).date().isoformat()
        await self.storage.seal_before(today)
        if not self.settings.recorder["summary_provider"]:
            return
        async with self.lock:
            for session in await self.storage.pending_sessions():
                if session["scope"] in self.resetting:
                    continue
                group_umo = f"{session['platform']}:GroupMessage:{session['group_id']}"
                if not self.settings.selected(session["umo"], group_umo):
                    continue
                pending = await self.storage.pending_messages(
                    session["scope"],
                    session["cursor"],
                    self.settings.recorder["window"],
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
                    self.active_scope = session["scope"]
                    started = perf_counter()
                    try:
                        await self.summarize(session, pending)
                    except Exception:
                        self.log.exception(
                            "summary.failed",
                            conversation=session["umo"]
                            if session["private"]
                            else group_umo,
                            message_count=0,
                            candidate_count=len(pending),
                            duration_seconds=round(perf_counter() - started, 3),
                        )
                    finally:
                        self.active_scope = None

    async def summarize(self, session: dict, pending: list[dict]):
        """Advance only over the rows actually included in the model request.

        Args:
            session: Persisted cursor and message counters.
            pending: Earliest retained messages after the cursor.
        """
        started = perf_counter()
        config = self.settings.recorder
        selected = []
        size = 0
        clipped = False
        filtered_seqs = set()
        for row in pending:
            if self.settings.is_command_record(row) or (
                self.robot_record_filter and await self.robot_record_filter(row)
            ):
                filtered_seqs.add(row["seq"])
                continue
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
            item["local_time"] = datetime.fromtimestamp(
                row["sent_at"], self.settings.timezone
            ).strftime("%Y-%m-%d %H:%M %z")
            # Clip an individual oversized message explicitly; never imply full coverage.
            if len(item["text"]) > config["context_chars"] // 2:
                item["text"] = (
                    item["text"][: config["context_chars"] // 2] + "[内容截断]"
                )
            cost = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
            if selected and size + cost > config["context_chars"]:
                break
            clipped |= item["text"] != row["text"]
            selected.append(item)
            size += cost
        if not selected:
            await self.storage.update_session(
                session["scope"],
                cursor=pending[-1]["seq"],
                summarized_count=pending[-1]["human_count"],
            )
            self.log.debug("summary.filtered.skipped", through_seq=pending[-1]["seq"])
            return
        self.log.info(
            "summary.start",
            conversation=self.log.identity(session["scope"]),
            pending_count=len(selected),
            cursor=session["cursor"],
        )
        now = datetime.now(self.settings.timezone)
        day = now.date().isoformat()
        diaries = await self.storage.diaries(
            session["scope"], budget=config["diary_context_chars"]
        )
        for diary in diaries:
            diary.pop("body")
        gap = pending[0]["seq"] > session["cursor"] + 1
        # Overlap supplies context without advancing already summarized messages.
        overlap = []
        if len(selected) < config["window"] and size < config["context_chars"]:
            preceding = await self.storage.preceding_messages(
                session["scope"], session["cursor"], config["window"] - len(selected)
            )
            for row in preceding:
                if self.settings.is_command_record(row) or (
                    self.robot_record_filter and await self.robot_record_filter(row)
                ):
                    continue
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
                item["local_time"] = datetime.fromtimestamp(
                    row["sent_at"], self.settings.timezone
                ).strftime("%Y-%m-%d %H:%M %z")
                cost = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
                if size + cost > config["context_chars"]:
                    break
                overlap.append(item)
                size += cost
        payload = {
            "date": day,
            "messages": list(reversed(overlap)) + selected,
            "already_summarized_through_seq": session["cursor"],
            "existing_diaries": diaries,
            "coverage_gap": gap or clipped,
            "output_char_limit": config["summary_output_chars"],
            "instruction": "只返回话题变更 JSON；历史日记仅供参考，旧日期消息在今日补记。",
        }
        self.log.debug(
            "summary.input", provider=config["summary_provider"], payload=payload
        )
        async with asyncio.timeout(config["summary_timeout"]):
            body = await self.generate(
                config["summary_provider"],
                self.prompt,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                purpose="recorder",
            )
        changes = DiaryProtocol.parse(
            body,
            payload["messages"],
            diaries,
            session["cursor"],
            day,
            config["summary_output_chars"],
        )
        committed_at = datetime.now(self.settings.timezone)
        if committed_at.date().isoformat() != day:
            raise ValueError(
                "Diary date changed during generation; retry on the new day"
            )
        through = selected[-1]["seq"]
        for row in pending:
            if row["seq"] <= through:
                continue
            if row["seq"] not in filtered_seqs:
                break
            through = row["seq"]
        count = next(row["human_count"] for row in pending if row["seq"] == through)
        await self.storage.commit_summary(
            session["scope"],
            day,
            changes,
            through,
            count,
            committed_at.timestamp(),
            coverage_gap=gap or clipped,
        )
        self.log.debug(
            "summary.output", changes=changes, through_seq=through, human_count=count
        )
        self.log.info(
            "summary.complete",
            conversation=session["umo"]
            if session["private"]
            else f"{session['platform']}:GroupMessage:{session['group_id']}",
            message_count=len(selected),
            context_count=len(payload["messages"]),
            added_topics=sum(change["action"] == "add" for change in changes),
            updated_topics=sum(change["action"] == "update" for change in changes),
            duration_seconds=round(perf_counter() - started, 3),
        )
