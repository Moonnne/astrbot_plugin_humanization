"""Humanization: bounded chat awareness and controlled native Agent replies."""

import asyncio
import time
import uuid
from contextlib import aclosing
from datetime import datetime
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import At, Plain
from astrbot.core.agent.tool import ToolSet
from astrbot.core.message.message_event_result import ResultContentType

from ..utils.output_protocol import OutputProtocol
from ..utils.plugin_log import PluginLog
from .astrbot_adapter import AstrBotAdapter, IdleEvent, ScopeFilter
from .controller.controller import Controller
from .controller.delivery import Delivery, ReplayResult
from .controller.prompts import Prompts
from .recorder.storage import Storage
from .recorder.summarizer import Summarizer
from .settings import Settings


class Runtime:
    def __init__(self, context, config: dict, data_dir: Path, console_logger=None):
        self.context = context
        self.config = config
        self.settings = Settings(config)
        self.log = PluginLog(
            data_dir / "log",
            self.settings.logging["debug"],
            console_logger if console_logger is not None else logger,
            self.settings.timezone,
        )
        self.adapter = AstrBotAdapter(context, self.settings, self.log)
        self.generation = uuid.uuid4().hex
        self.tasks = set()
        self.active = set()
        self.closed = False
        self.storage = Storage(
            data_dir / "chat" / "db" / "chat.sqlite3",
            self.settings.recorder["retention"],
            self.log,
        )
        self.prompts = Prompts(self.settings, self.storage, context.persona_manager)
        self.controller = Controller(
            self.settings, self.storage, self.adapter.generate, self.prompts, self.log
        )
        self.delivery = Delivery(self.storage, self.settings)
        self.summarizer = Summarizer(
            self.storage,
            self.settings,
            self.adapter.generate,
            self.prompts.text["summary"],
            self.log,
        )

    async def initialize(self):
        await self.log.open()
        self.log.info(
            "runtime.start",
            debug=self.log.debug_mode,
            retention=self.settings.recorder["retention"],
            selected_sessions=len(
                self.settings.scope["sessions"] + self.settings.scope["manual_sessions"]
            ),
        )
        self.log.debug(
            "configuration.loaded",
            configuration=self.config,
            prompt_resources=sorted(self.prompts.text),
        )
        try:
            for name in ("behavior", "expression", "group", "private"):
                await self.prompts.fragment(name)
            await self.storage.open()
        except Exception:
            self.log.exception("runtime.initialize.failed")
            await self.log.close()
            raise
        ScopeFilter.settings = self.settings
        if self.settings.recorder["enabled"]:
            self.tasks.add(
                asyncio.create_task(self.summary_loop(), name="humanization-summary")
            )
            if (
                self.settings.controller["enabled"]
                and self.settings.proactive["enabled"]
            ):
                self.tasks.add(
                    asyncio.create_task(self.idle_loop(), name="humanization-idle")
                )

    async def observe(self, event: AstrMessageEvent):
        if self.closed:
            return
        idle = event.get_extra("humanization_idle")
        if idle:
            if idle["generation"] != self.generation:
                event.stop_event()
                return
            event.should_call_llm(True)
            async with aclosing(self.turn(event, idle=True)) as generator:
                async for request in generator:
                    yield request
            event.stop_event()
            return
        if str(event.get_self_id()) == str(event.get_sender_id()):
            return
        command = self.adapter.is_command(event)
        self.log.debug(
            "message.inspect",
            command=command,
            umo=event.unified_msg_origin,
            text=event.message_str,
        )
        event.set_extra("humanization_command", command)
        if (
            not command
            and self.settings.controller["enabled"]
            and await self.adapter.can_reply(event)
        ):
            event.should_call_llm(True)
            event.set_extra("humanization_claimed", True)
            self.log.debug("message.claimed", default_llm_suppressed=True)
        if command and self.settings.recorder["filter_commands"]:
            message = self.adapter.snapshot(event)
            await self.storage.update_session(
                message.scope, last_human=message.received_at, idle_waiting=0
            )
            self.log.debug("message.filtered", reason="command")
            return
        message = self.adapter.snapshot(event)
        if await self.storage.append(message):
            event.set_extra("humanization_message", message)
            self.log.debug(
                "message.recorded",
                message_id=message.message_id,
                scope=message.scope,
                text=message.text,
            )
        else:
            self.log.debug("message.filtered", reason="duplicate")

    async def participate(self, event: AstrMessageEvent):
        if self.closed or not event.get_extra("humanization_claimed"):
            return
        if event.get_extra("humanization_command") or event._has_send_oper:
            return
        async with aclosing(self.turn(event)) as generator:
            async for request in generator:
                yield request

    async def turn(self, event, idle: bool = False):
        """Hold group ownership across the native pipeline's generator yield.

        Args:
            event: A real incoming event or a marked scheduler event.
            idle: Whether a quiet-group trigger initiated this turn.

        Yields:
            A native ProviderRequest if participation is granted.
        """
        message = (
            self.adapter.snapshot(event)
            if idle
            else event.get_extra("humanization_message")
        )
        if message is None:
            return
        task = asyncio.current_task()
        self.active.add(task)
        run = None
        turn = None
        previous_streaming = event.get_extra("enable_streaming")
        try:
            async with self.log.context("reply"), self.controller.lock(message.scope):
                if self.closed or not await self.adapter.can_reply(event):
                    return
                session = await self.storage.session(message.scope)
                direct_at = any(
                    isinstance(p, At) and str(p.qq) == message.self_id
                    for p in event.get_messages()
                )
                if idle:
                    if session["last_human"] != event.get_extra("humanization_idle")[
                        "last_human"
                    ] or not self.controller.idle_due(
                        session,
                        datetime.now(self.settings.timezone),
                        check_schedule=False,
                    ):
                        return
                else:
                    await asyncio.sleep(self.settings.controller["debounce_seconds"])
                    session = await self.storage.session(message.scope)
                    if not direct_at and session["last_human"] > message.received_at:
                        self.log.debug("reply.skipped", reason="newer_message")
                        return
                mentioned = any(
                    name and name in message.text
                    for name in self.settings.controller["names"]
                )
                decision = await self.controller.decide(
                    message, direct_at, mentioned, idle
                )
                if not decision.reply:
                    self.log.debug("reply.skipped", reason="gate_wait")
                    return
                run = await self.storage.start_reply(
                    message.scope, time.time(), "idle" if idle else "message"
                )
                self.log.info(
                    "reply.start",
                    run=run,
                    trigger="idle" if idle else "message",
                    conversation=self.log.identity(message.scope),
                )
                turn = {
                    "message": message,
                    "run": run,
                    "idle": idle,
                    "intent": decision.intent,
                    "phase": "agent",
                    "outputs": [],
                    "recorded": set(),
                    "status": "not_sent",
                }
                event.set_extra("humanization_turn", turn)
                event.set_extra("enable_streaming", False)
                request = await self.adapter.request(event)
                self.log.debug(
                    "agent.request.prepared", available=request is not None, run=run
                )
                if request:
                    yield request
                # The native Agent has now completed its tool loop, statistics,
                # and history writer. Each result resumes the normal downstream stages.
                turn["phase"] = "replay"
                self.log.debug(
                    "agent.complete", run=run, cached_results=len(turn["outputs"])
                )
                for index, chain in enumerate(turn["outputs"]):
                    if event.is_stopped() or event.get_extra("agent_user_aborted"):
                        break
                    if idle:
                        session = await self.storage.session(message.scope)
                        if (
                            session["last_human"]
                            != event.get_extra("humanization_idle")["last_human"]
                        ):
                            turn["status"] = "superseded"
                            break
                    turn["index"] = index
                    self.log.debug(
                        "reply.bubble.submit",
                        run=run,
                        index=index,
                        components=[part.type for part in chain],
                    )
                    yield ReplayResult(
                        chain=list(chain),
                        result_content_type=ResultContentType.LLM_RESULT,
                    )
                    if index not in turn["recorded"]:
                        # Native send hooks are completion notifications, not delivery receipts.
                        if turn["status"] != "superseded":
                            turn["status"] = "unconfirmed"
                        break
                await self.storage.finish_reply(
                    run, turn["status"], len(turn["recorded"])
                )
                self.log.info(
                    "reply.complete",
                    run=run,
                    status=turn["status"],
                    completed_parts=len(turn["recorded"]),
                )
        except (asyncio.CancelledError, GeneratorExit):
            if run is not None:
                await self.storage.finish_reply(run, "unknown", len(turn["recorded"]))
                self.log.info(
                    "reply.interrupted", run=run, completed_parts=len(turn["recorded"])
                )
            raise
        except Exception:
            if run is not None:
                await self.storage.finish_reply(run, "failed", len(turn["recorded"]))
            self.log.exception("reply.failed", run=run)
        finally:
            if turn is not None:
                # Release all cached component references even on cancellation.
                turn.clear()
                event.set_extra("humanization_turn", None)
                event.set_extra("enable_streaming", previous_streaming)
                self.log.debug("reply.cache.cleared", run=run)
            self.active.discard(task)

    async def inject(self, event, request):
        turn = event.get_extra("humanization_turn")
        if not turn:
            return
        message = turn["message"]
        request.system_prompt += "\n\n" + await self.prompts.reply(message.private)
        context = await self.prompts.context(message.scope, message.message_id)
        self.log.info("context.prepare", run=turn["run"], context_chars=len(context))
        self.adapter.inject_observation(request, context, turn["intent"])
        blocked = self.settings.controller["blocked_tools"]
        if request.func_tool and blocked:
            request.func_tool = ToolSet(
                [tool for tool in request.func_tool.tools if tool.name not in blocked]
            )
        self.log.debug(
            "agent.request.injected",
            run=turn["run"],
            system_prompt=request.system_prompt,
            prompt=request.prompt,
            observation=context,
            intent=turn["intent"],
            tools=request.func_tool.names() if request.func_tool else [],
            image_count=len(request.image_urls or []),
            audio_count=len(request.audio_urls or []),
            history=request.contexts,
            model=request.model,
        )

    async def validate(self, event, response):
        turn = event.get_extra("humanization_turn")
        if not turn or response.role != "assistant":
            return
        self.log.debug(
            "agent.response",
            run=turn["run"],
            text=response.completion_text,
            components=[part.type for part in response.result_chain.chain]
            if response.result_chain
            else [],
        )
        source = (
            response.result_chain.chain
            if response.result_chain
            else [Plain(response.completion_text)]
        )
        # Only spoken text is constrained; media stays in its original order.
        chunks = []
        for part in source:
            if isinstance(part, Plain):
                if chunks and isinstance(chunks[-1], str):
                    chunks[-1] += part.text
                else:
                    chunks.append(part.text)
            else:
                chunks.append(part)
        outputs = []
        text_count = 0
        repaired_once = False
        for chunk in chunks:
            if not isinstance(chunk, str):
                if outputs:
                    outputs[-1].append(chunk)
                else:
                    outputs.append([chunk])
                continue
            if not chunk.strip():
                continue
            try:
                bubbles = OutputProtocol.parse(chunk)
            except ValueError:
                if repaired_once:
                    turn["status"] = "filtered"
                    continue
                repaired_once = True
                self.log.debug("output.repair.start", run=turn["run"], original=chunk)
                try:
                    provider = await self.context.get_current_chat_provider_id(
                        event.unified_msg_origin
                    )
                    async with asyncio.timeout(
                        self.settings.controller["gate_timeout"]
                    ):
                        repaired = await self.adapter.generate(
                            provider,
                            self.prompts.text["output"]
                            + "\n只修复给定文本的格式，保留原意，不回答其中的要求。",
                            chunk,
                        )
                    bubbles = OutputProtocol.parse(repaired)
                except Exception:
                    self.log.exception("output.filtered", run=turn["run"])
                    turn["status"] = "filtered"
                    continue
            text_count += len(bubbles)
            if text_count > 3:
                turn["status"] = "filtered"
                continue
            if outputs and all(not isinstance(p, Plain) for p in outputs[-1]):
                outputs[-1].append(Plain(bubbles[0]))
                bubbles = bubbles[1:]
            outputs.extend([[Plain(bubble)] for bubble in bubbles])
        turn["outputs"] = outputs
        self.log.debug(
            "output.validated",
            run=turn["run"],
            result_count=len(outputs),
            status=turn["status"],
        )

    async def defer_result(self, event):
        """Defer this Agent's model output until its native invocation returns.

        Args:
            event: Native event carrying the active Humanization turn.
        """
        turn = event.get_extra("humanization_turn")
        result = event.get_result()
        if not turn or not result or event.is_stopped():
            return
        if turn["phase"] == "agent" and result.is_llm_result():
            # This includes text yielded before the completion hook in skills_like
            # mode. Tool notifications and general/error results are untouched.
            event.clear_result()
            self.log.debug("output.deferred", run=turn["run"])
        elif turn["phase"] == "replay" and turn["idle"]:
            session = await self.storage.session(turn["message"].scope)
            if (
                session["last_human"]
                != event.get_extra("humanization_idle")["last_human"]
            ):
                turn["status"] = "superseded"
                event.clear_result()

    async def after_sent(self, event):
        turn = event.get_extra("humanization_turn")
        if turn and turn["phase"] == "replay" and event.get_result():
            await self.delivery.record(event, turn)
            self.log.debug(
                "reply.native_stage.complete", run=turn["run"], index=turn["index"]
            )

    async def summary_loop(self):
        while True:
            try:
                await self.summarizer.tick()
            except Exception:
                self.log.exception("summary.worker.failed")
            await asyncio.sleep(15)

    async def idle_loop(self):
        while True:
            await asyncio.sleep(self.settings.proactive["check_minutes"] * 60)
            try:
                now = datetime.now(self.settings.timezone)
                for session in await self.storage.rows(
                    "SELECT * FROM sessions WHERE private=0"
                ):
                    group_umo = (
                        f"{session['platform']}:GroupMessage:{session['group_id']}"
                    )
                    # Idle turns require group-wide opt-in, not one member's isolated UMO.
                    if not self.settings.selected(
                        group_umo, group_umo
                    ) or not self.controller.idle_due(session, now):
                        continue
                    if self.controller.lock(session["scope"]).locked():
                        self.log.debug(
                            "idle.skipped",
                            reason="reply_busy",
                            conversation=self.log.identity(session["scope"]),
                        )
                        continue
                    await self.storage.update_session(
                        session["scope"],
                        next_idle=now.timestamp()
                        + self.settings.proactive["check_minutes"] * 60,
                    )
                    for platform in self.context.platform_manager.get_insts():
                        if platform.meta().id == session["platform"]:
                            event = IdleEvent(
                                self.context, platform.meta(), session, self.generation
                            )
                            await self.context.get_event_queue().put(event)
                            self.log.debug(
                                "idle.queued",
                                conversation=self.log.identity(session["scope"]),
                            )
                            break
            except Exception:
                self.log.exception("idle.worker.failed")

    async def terminate(self):
        self.closed = True
        if ScopeFilter.settings is self.settings:
            ScopeFilter.settings = None
        tasks = self.tasks | self.active
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await self.storage.close()
        finally:
            self.log.info("runtime.stop")
            await self.log.close()
