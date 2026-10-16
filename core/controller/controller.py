"""Per-conversation turn ownership and shared semantic participation."""

import asyncio
import json
import random
from datetime import datetime
from time import perf_counter

from ...models.decision import Decision
from .protocol import ControllerProtocol


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
        required = forced and not idle
        fallback = Decision(
            True, "回应这条明确叫你的消息；仍可按角色意愿拒绝任务", "forced"
        )
        if (
            not required
            and now.timestamp() - session["last_reply"] < cfg["cooldown_seconds"]
        ):
            self.log.debug("gate.wait", reason="cooldown")
            return Decision(False, reason="cooldown")
        activity = self.settings.effective_activity(
            message.private, direct_at, mentioned, now
        )
        if idle:
            activity *= self.settings.proactive["probability"]
        sample = (
            self.random.random()
            if not required and cfg["mode"] == "probability"
            else None
        )
        self.log.debug(
            "gate.check",
            activity=activity,
            mode=cfg["mode"],
            sample=sample,
            idle=idle,
            direct_at=direct_at,
            mentioned=mentioned,
            reply_required=required,
        )
        if not required and (
            activity == 0 or (sample is not None and sample >= activity)
        ):
            self.log.debug("gate.wait", reason="random_sample")
            return Decision(False, reason="random_sample")
        provider = cfg["gate_provider"]
        if not provider:
            self.log.debug("gate.wait", reason="no_provider", reply_required=required)
            return fallback if required else Decision(False, reason="no_provider")
        conversation = (
            message.umo
            if message.private
            else f"{message.platform}:GroupMessage:{message.group_id}"
        )
        started = perf_counter()
        try:
            system = await self.prompts.gate(message.private)
            through = (
                scheduled.sequence if scheduled is not None else session["last_seq"]
            )
            context = json.loads(
                await self.prompts.context(
                    message.scope, through_seq=through, for_controller=True
                )
            )
            history = []
            for row in await self.storage.decisions(message.scope):
                previous = row["decision"]
                plan = previous["plan"]
                history.append(
                    {
                        "time": datetime.fromtimestamp(
                            row["created_at"], self.settings.timezone
                        ).isoformat(),
                        "last_human_at": datetime.fromtimestamp(
                            row["last_human_at"], self.settings.timezone
                        ).isoformat(),
                        "observed_through_seq": row["observed_through_seq"],
                        "reply": previous["reply"],
                        "reason": previous["reason"],
                        "emotion": previous["emotion"],
                        "outcome": row["outcome"],
                        "focus": {
                            "message_id": plan["target_message_id"],
                            "topic_id": plan["topic_id"],
                        }
                        if plan
                        else None,
                    }
                )
            payload = json.dumps(
                {
                    "context": context,
                    "recent_decisions": history,
                    "now": now.isoformat(),
                    "trigger": "idle" if idle else "message",
                    "target": message.message_id,
                    "bot_id": message.self_id,
                    "direct_at": direct_at,
                    "mentioned": mentioned,
                    "reply_required": required,
                    "activity": activity,
                    "since_last_human_seconds": max(
                        0, now.timestamp() - session["last_human"]
                    )
                    if session["last_human"]
                    else None,
                    "since_last_reply_seconds": max(
                        0, now.timestamp() - session["last_reply"]
                    )
                    if session["last_reply"]
                    else None,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            async with asyncio.timeout(cfg["gate_timeout"]):
                raw = await self.generate(
                    provider, system, payload, purpose="controller"
                )
            result = ControllerProtocol.parse(raw, context, required)
            plan = result["plan"]
            focus = None
            if plan:
                focus = {
                    "message": next(
                        (
                            row
                            for row in context["messages"]
                            if row["message_id"] == plan["target_message_id"]
                        ),
                        None,
                    ),
                    "topic": next(
                        (
                            row
                            for row in context["topics"]["items"]
                            if row["id"] == plan["topic_id"]
                        ),
                        None,
                    ),
                }
            record_id = await self.storage.record_decision(
                message.scope,
                result,
                datetime.now(self.settings.timezone).timestamp(),
                through,
                session["last_human"],
                "idle" if idle else "message",
                required,
            )
            self.log.debug("gate.decision", decision=result, record_id=record_id)
            self.log.info(
                "gate.complete",
                conversation=conversation,
                action="reply" if result["reply"] else "wait",
                emotion=result["emotion"]["primary"],
                intensity=result["emotion"]["intensity"],
                participation=plan["participation"] if plan else None,
                duration_seconds=round(perf_counter() - started, 3),
            )
            return Decision(
                result["reply"],
                plan["guidance"] if plan else "",
                "reply" if result["reply"] else "semantic_wait",
                result,
                focus,
                record_id,
            )
        except Exception:
            self.log.exception(
                "gate.failed",
                conversation=conversation,
                action="reply" if required else "wait",
                duration_seconds=round(perf_counter() - started, 3),
            )
            return fallback if required else Decision(False, reason="error")

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
