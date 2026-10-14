"""Per-conversation turn ownership and shared semantic participation."""

import asyncio
import json
import random
from datetime import datetime
from time import perf_counter

from ..models import Decision


class Controller:
    def __init__(self, settings, storage, generate, prompts, log):
        self.settings = settings
        self.storage = storage
        self.generate = generate
        self.prompts = prompts
        self.log = log
        self.locks = {}
        self.random = random.Random()

    def lock(self, scope: str) -> asyncio.Lock:
        return self.locks.setdefault(scope, asyncio.Lock())

    async def decide(
        self,
        message,
        direct_at: bool,
        mentioned: bool,
        idle: bool = False,
        scheduled=None,
    ) -> Decision:
        cfg = self.settings.controller
        session = await self.storage.session(message.scope)
        now = datetime.now(self.settings.timezone)
        forced = (
            scheduled.forced
            if scheduled is not None
            else self.settings.forced(direct_at, mentioned)
        )
        if not idle and forced:
            self.log.debug("gate.direct_reply", reason="force_at_or_name")
            return Decision(
                True, "回应这条明确叫你的消息；仍可按角色意愿拒绝任务", "forced"
            )
        if now.timestamp() - session["last_reply"] < cfg["cooldown_seconds"]:
            self.log.debug("gate.wait", reason="cooldown")
            return Decision(False, reason="cooldown")
        activity = self.settings.effective_activity(
            message.private, direct_at, mentioned, now
        )
        if idle:
            activity *= self.settings.proactive["probability"]
        sample = self.random.random() if cfg["mode"] == "probability" else None
        self.log.debug(
            "gate.check",
            activity=activity,
            mode=cfg["mode"],
            sample=sample,
            idle=idle,
            direct_at=direct_at,
            mentioned=mentioned,
        )
        if activity == 0 or (sample is not None and sample >= activity):
            self.log.debug("gate.wait", reason="random_sample")
            return Decision(False, reason="random_sample")
        provider = cfg["gate_provider"]
        if not provider:
            self.log.debug("gate.wait", reason="no_provider")
            return Decision(False, reason="no_provider")
        system = await self.prompts.gate(message.private)
        context = (
            await self.prompts.context(message.scope, through_seq=scheduled.sequence)
            if scheduled is not None
            else await self.prompts.context(message.scope)
        )
        payload = json.dumps(
            {
                "context": json.loads(context),
                "trigger": "idle" if idle else "message",
                "target": message.message_id,
                "bot_id": message.self_id,
                "activity": activity,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        conversation = (
            message.umo
            if message.private
            else f"{message.platform}:GroupMessage:{message.group_id}"
        )
        started = perf_counter()
        try:
            async with asyncio.timeout(cfg["gate_timeout"]):
                raw = await self.generate(
                    provider, system, payload, purpose="controller"
                )
            raw = raw.strip()
            if raw.startswith("```") and raw.endswith("```"):
                raw = "\n".join(raw.splitlines()[1:-1])
            result = json.loads(raw)
            if result["action"] not in ("reply", "wait") or not isinstance(
                result.get("intent", ""), str
            ):
                raise ValueError("Invalid gate decision")
            self.log.debug(
                "gate.decision",
                action=result["action"],
                intent=result.get("intent", ""),
            )
            self.log.info(
                "gate.complete",
                conversation=conversation,
                action=result["action"],
                intent=result.get("intent", "")[:120],
                duration_seconds=round(perf_counter() - started, 3),
            )
            return Decision(
                result["action"] == "reply",
                result.get("intent", "")[:500],
                "reply" if result["action"] == "reply" else "semantic_wait",
            )
        except Exception:
            self.log.exception(
                "gate.failed",
                conversation=conversation,
                action="wait",
                duration_seconds=round(perf_counter() - started, 3),
            )
            return Decision(False, reason="error")

    def idle_due(
        self, session: dict, now: datetime, check_schedule: bool = True
    ) -> bool:
        cfg = self.settings.proactive
        if not cfg["enabled"] or session["private"] or session["idle_waiting"]:
            self.log.debug("idle.skipped", reason="disabled_private_or_unanswered")
            return False
        if self.settings.quiet(now) or self.settings.activity(False, now) == 0:
            self.log.debug("idle.skipped", reason="quiet_or_zero_activity")
            return False
        if check_schedule and now.timestamp() < session["next_idle"]:
            self.log.debug("idle.skipped", reason="check_interval")
            return False
        if now.timestamp() - session["last_human"] < cfg["idle_minutes"] * 60:
            self.log.debug("idle.skipped", reason="recent_human_activity")
            return False
        if now.timestamp() - session["last_reply"] < cfg["interval_minutes"] * 60:
            self.log.debug("idle.skipped", reason="recent_bot_activity")
            return False
        eligible = (
            session["idle_day"] != now.date().isoformat()
            or session["idle_count"] < cfg["daily_limit"]
        )
        self.log.debug(
            "idle.evaluated",
            eligible=eligible,
            daily_count=session["idle_count"],
            daily_limit=cfg["daily_limit"],
        )
        return eligible
