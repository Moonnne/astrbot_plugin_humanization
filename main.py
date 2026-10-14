"""AstrBot lifecycle and event registration for Humanization."""

from contextlib import aclosing
from sys import maxsize

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .core.astrbot_adapter import InternalEventFilter, ScopeFilter
from .core.management import ManagementAccessFilter, ManagementMessageFilter
from .core.runtime import Runtime


class Humanization(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.runtime = Runtime(context, config, StarTools.get_data_dir(), self.logger)
        restored = False
        for name in ("behavior", "expression", "group", "private"):
            if not config["prompts"][name].strip():
                config["prompts"][name] = config.schema["prompts"]["items"][name][
                    "default"
                ]
                restored = True
        if restored:
            config.save_config()

    async def initialize(self):
        await self.runtime.initialize()
        try:
            await self.refresh_sessions()
        except Exception:
            await self.runtime.terminate()
            raise

    @filter.on_astrbot_loaded()
    async def refresh_sessions(self):
        choices = await self.runtime.adapter.session_options()
        choices.update(
            {umo: choices.get(umo, umo) for umo in self.config["scope"]["sessions"]}
        )
        item = self.config.schema["scope"]["items"]["sessions"]
        item["options"] = list(choices)
        item["labels"] = list(choices.values())
        self.runtime.log.debug("scope.options.updated", option_count=len(choices))
        items = self.config.schema["controller"]["items"]
        for key in ("group", "private"):
            items[key]["hint"] = (
                self.runtime.settings.frequency_hint(self.config["controller"][key])
                + "\n调度对照：0.1≈每10条、0.2≈每5条、0.5≈每2条、0.8≈每1.25条评估；0不评估。保存重载后更新当前估计。"
            )
        estimates = [
            f"{period['name']} {period['start']}—{period['end']}：群聊 {self.runtime.settings.frequency_hint(period['group'])} 私聊 {self.runtime.settings.frequency_hint(period['private'])}"
            for period in self.config["controller"]["periods"]
        ]
        items["periods"]["hint"] = "保存重载并重新打开配置页后更新。\n" + "\n".join(
            estimates
        )

    @filter.custom_filter(ManagementMessageFilter, priority=20000)
    async def management_guard(self, event: AstrMessageEvent):
        event.should_call_llm(True)
        event.set_extra("humanization_management", True)
        if not self.runtime.admin.allowed(event):
            event.stop_event()

    @filter.custom_filter(ManagementAccessFilter)
    @filter.command_group("hum")
    def hum(self):
        """Humanization administration."""

    @hum.custom_filter(ManagementAccessFilter)
    @hum.command("clear", alias={"claer"})
    @filter.permission_type(filter.PermissionType.ADMIN, raise_error=False)
    async def clear_log(self, event: AstrMessageEvent, target: str = ""):
        text = await self.runtime.admin.clear_log(event, target)
        if text:
            yield event.plain_result(text)
        event.stop_event()

    @hum.custom_filter(ManagementAccessFilter)
    @hum.command("reset_data")
    @filter.permission_type(filter.PermissionType.ADMIN, raise_error=False)
    async def reset_data(self, event: AstrMessageEvent, mode: str = ""):
        text = await self.runtime.admin.request_reset(event, mode)
        if text:
            yield event.plain_result(text)
        event.stop_event()

    @hum.custom_filter(ManagementAccessFilter)
    @hum.command("IClearKnowWhatIDoingNow")
    @filter.permission_type(filter.PermissionType.ADMIN, raise_error=False)
    async def confirm_reset(self, event: AstrMessageEvent):
        text = await self.runtime.admin.confirm(event)
        if text:
            yield event.plain_result(text)
        event.stop_event()

    @filter.custom_filter(ScopeFilter, priority=10000)
    async def observe(self, event: AstrMessageEvent):
        async with aclosing(self.runtime.observe(event)) as generator:
            async for result in generator:
                yield result

    # Run internal events before the host's incoming-message recorder and waiters.
    @filter.custom_filter(InternalEventFilter, priority=maxsize + 1)
    async def scheduled_event(self, event: AstrMessageEvent):
        try:
            async with aclosing(self.runtime.observe(event)) as generator:
                async for result in generator:
                    yield result
        finally:
            event.stop_event()

    @filter.custom_filter(ScopeFilter, priority=-10000)
    async def participate(self, event: AstrMessageEvent):
        async with aclosing(self.runtime.participate(event)) as generator:
            async for result in generator:
                yield result

    @filter.on_llm_request(priority=-10000)
    async def inject(self, event, request):
        await self.runtime.inject(event, request)

    @filter.on_agent_begin(priority=-10000)
    async def filter_agent_history(self, event, run_context):
        self.runtime.adapter.filter_agent_history(event, run_context)

    @filter.on_agent_done(priority=-10000)
    async def restore_agent_history(self, event, run_context, response):
        self.runtime.adapter.record_main_usage(event)
        self.runtime.adapter.restore_agent_history(event, run_context)

    @filter.on_llm_response(priority=-10000)
    async def validate(self, event, response):
        await self.runtime.validate(event, response)

    @filter.on_decorating_result(priority=10000)
    async def defer_result(self, event):
        await self.runtime.defer_result(event)

    @filter.after_message_sent(priority=10000)
    async def after_sent(self, event):
        await self.runtime.after_sent(event)

    @filter.on_using_llm_tool(priority=10000)
    async def tool_started(self, event, tool, tool_args):
        turn = event.get_extra("humanization_turn")
        if turn:
            self.runtime.adapter.record_main_usage(event)
            self.runtime.log.debug(
                "tool.start", tool=tool.name, arguments=tool_args, run=turn["run"]
            )

    @filter.on_llm_tool_respond(priority=10000)
    async def tool_finished(self, event, tool, tool_args, tool_result):
        turn = event.get_extra("humanization_turn")
        if turn and self.runtime.log.debug_mode:
            result = []
            if tool_result:
                for part in tool_result.content:
                    result.append(
                        {"type": part.type, "text": part.text}
                        if part.type == "text"
                        else {"type": part.type}
                    )
            self.runtime.log.debug(
                "tool.complete",
                tool=tool.name,
                result=result,
                structured_result=tool_result.structuredContent
                if tool_result
                else None,
                is_error=tool_result.isError if tool_result else False,
                run=turn["run"],
            )

    async def terminate(self):
        await self.runtime.terminate()
