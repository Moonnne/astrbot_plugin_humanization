"""AstrBot lifecycle and event registration for Humanization."""

from contextlib import aclosing

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .core.astrbot_adapter import ScopeFilter
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

    @filter.custom_filter(ScopeFilter, priority=10000)
    async def observe(self, event: AstrMessageEvent):
        async with aclosing(self.runtime.observe(event)) as generator:
            async for result in generator:
                yield result

    @filter.custom_filter(ScopeFilter, priority=-10000)
    async def participate(self, event: AstrMessageEvent):
        async with aclosing(self.runtime.participate(event)) as generator:
            async for result in generator:
                yield result

    @filter.on_llm_request(priority=-10000)
    async def inject(self, event, request):
        await self.runtime.inject(event, request)

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
