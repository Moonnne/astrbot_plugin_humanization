"""Per-conversation turn ownership and probabilistic participation."""

import asyncio
import json
import random
from datetime import datetime

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
        self, message, direct_at: bool, mentioned: bool, idle: bool = False
    ) -> Decision:
        cfg = self.settings.controller
        session = await self.storage.session(message.scope)
        now = datetime.now(self.settings.timezone)
        if direct_at and cfg["at_weight"] == 1:
            self.log.debug("gate.direct_reply", reason="at_weight_one")
            return Decision(True, "回应这条明确 @ 你的消息")
        if now.timestamp() - session["last_reply"] < cfg["cooldown_seconds"]:
            self.log.debug("gate.wait", reason="cooldown")
            return Decision(False)
        probability = self.settings.activity(message.private, now)
        if direct_at:
            probability = max(probability, cfg["at_weight"])
        elif mentioned:
            probability = max(probability, cfg["mention_weight"])
        if idle:
            probability *= self.settings.proactive["probability"]
        sample = self.random.random()
        self.log.debug(
            "gate.sample",
            probability=probability,
            sample=sample,
            idle=idle,
            direct_at=direct_at,
            mentioned=mentioned,
        )
        if sample >= probability:
            self.log.debug("gate.wait", reason="random_sample")
            return Decision(False)
        provider = cfg["gate_provider"]
        if not provider:
            self.log.debug("gate.wait", reason="no_provider")
            return Decision(False)
        system = await self.prompts.gate(message.private)
        context = await self.prompts.context(message.scope)
        payload = json.dumps(
            {
                "trigger": "idle" if idle else "message",
                "target": message.message_id,
                "activity": probability,
                "context": context,
            },
            ensure_ascii=False,
        )
        try:
            async with asyncio.timeout(cfg["gate_timeout"]):
                raw = await self.generate(provider, system, payload)
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
            return Decision(result["action"] == "reply", result.get("intent", "")[:500])
        except Exception:
            self.log.exception("gate.failed", action="wait")
            return Decision(False)

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
