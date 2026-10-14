"""Integration with AstrBot's native request collector and event interfaces."""

import json
import time
import uuid
from datetime import datetime

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Plain, Reply
from astrbot.core.agent.message import TextPart
from astrbot.core.astr_main_agent import MainAgentBuildConfig, collect_initial_request
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.session_llm_manager import SessionServiceManager
from astrbot.core.star.session_plugin_manager import SessionPluginManager

from .models import Message


class ScopeFilter(filter.CustomFilter):
    settings = None

    def filter(self, event, cfg) -> bool:
        settings = type(self).settings
        if (
            settings is None
            or not settings.recorder["enabled"]
            or event.get_platform_name() != "aiocqhttp"
        ):
            return False
        if event.get_message_type() not in (
            MessageType.GROUP_MESSAGE,
            MessageType.FRIEND_MESSAGE,
        ):
            return False
        group_umo = f"{event.get_platform_id()}:GroupMessage:{event.get_group_id()}"
        return settings.selected(event.unified_msg_origin, group_umo)


class IdleEvent(AstrMessageEvent):
    """A scheduler event using the group's shared route, never a member's UMO."""

    def __init__(self, context, platform_meta, session: dict, generation: str):
        message = AstrBotMessage()
        message.type = MessageType.GROUP_MESSAGE
        message.self_id = session["self_id"]
        message.session_id = session["group_id"]
        message.group_id = session["group_id"]
        message.message_id = uuid.uuid4().hex
        message.sender = MessageMember(
            user_id="humanization", nickname="Humanization Scheduler"
        )
        message.message = [Plain("根据当前群聊情况，自然地发起一次简短对话")]
        message.message_str = message.message[0].text
        message.timestamp = int(time.time())
        self.route = MessageSession(
            session["platform"], MessageType.GROUP_MESSAGE, session["group_id"]
        )
        # EventBus must select the group's config before member isolation runs.
        super().__init__(
            message.message_str, message, platform_meta, session["group_id"]
        )
        self.context = context
        self.set_extra(
            "humanization_idle",
            {"generation": generation, "last_human": session["last_human"]},
        )

    @property
    def unified_msg_origin(self):
        # Member isolation must not change the scheduled group's configuration.
        return str(self.route)

    async def send(self, message):
        if not await self.context.send_message(self.route, message):
            raise RuntimeError("Active OneBot platform not found")
        await super().send(message)


class AstrBotAdapter:
    def __init__(self, context, settings, log):
        self.context = context
        self.settings = settings
        self.log = log

    def snapshot(self, event) -> Message:
        private = event.is_private_chat()
        group = str(event.get_group_id() or "")
        platform = event.get_platform_id()
        scope = json.dumps(
            [
                platform,
                event.get_self_id(),
                "private" if private else "group",
                event.get_sender_id() if private else group,
            ],
            ensure_ascii=False,
        )
        segments = []
        rendered = []
        for part in event.get_messages():
            if isinstance(part, Plain):
                segments.append({"type": "text", "text": part.text})
                rendered.append(part.text)
            elif isinstance(part, At):
                segments.append({"type": "at", "id": str(part.qq)})
                rendered.append(f"[@{part.qq}]")
            else:
                tag = part.type.lower()
                segments.append({"type": tag})
                rendered.append(f"[{tag}]")
        now = time.time()
        return Message(
            scope=scope,
            umo=event.unified_msg_origin,
            platform=platform,
            self_id=str(event.get_self_id()),
            group_id=group,
            sender_id=str(event.get_sender_id()),
            sender_name=event.get_sender_name(),
            message_id=str(event.message_obj.message_id or ""),
            sent_at=float(event.message_obj.timestamp or now),
            received_at=now,
            text="".join(rendered),
            segments=json.dumps(segments, ensure_ascii=False),
            private=private,
            day=datetime.fromtimestamp(now, self.settings.timezone).date().isoformat(),
        )

    def is_command(self, event) -> bool:
        handlers = event.get_extra("activated_handlers") or []
        if any(
            isinstance(f, (CommandFilter, CommandGroupFilter))
            for handler in handlers
            for f in handler.event_filters
        ):
            return True
        # WakingCheck may have stripped a wake prefix from message_str.
        raw = "".join(
            p.text for p in event.get_messages() if isinstance(p, Plain)
        ).lstrip()
        return self.settings.is_command_text(raw)

    def filter_command_history(self, event, request):
        """Remove identifiable command inputs from this plugin's model request.

        Args:
            event: Incoming non-command event supplying any quoted message.
            request: Native request whose resulting history is saved by AstrBot.
        """
        if not self.settings.recorder["filter_commands"]:
            return
        retained = []
        excluded = False
        for item in request.contexts:
            if item["role"] == "user":
                content = item.get("content") or ""
                text = (
                    content
                    if isinstance(content, str)
                    else "\n".join(
                        part.get("text", "")
                        for part in content
                        if part.get("type") == "text"
                    )
                )
                excluded = self.settings.is_command_text(text)
            if not excluded:
                retained.append(item)
        removed = len(request.contexts) - len(retained)
        request.contexts = retained
        for part in event.get_messages():
            if not isinstance(part, Reply):
                continue
            quoted = (
                "".join(
                    entry.text for entry in part.chain or () if isinstance(entry, Plain)
                )
                or part.message_str
                or ""
            )
            if self.settings.is_command_text(quoted):
                request.extra_user_content_parts = [
                    entry
                    for entry in request.extra_user_content_parts
                    if not (
                        isinstance(entry, TextPart)
                        and entry.text.startswith("<Quoted Message>\n")
                    )
                ]
        self.log.debug("context.commands.filtered", removed_history_items=removed)

    async def can_reply(self, event) -> bool:
        if isinstance(event, IdleEvent):
            route = str(event.route)
            if not await SessionServiceManager.is_session_enabled(
                route
            ) or not await SessionServiceManager.is_llm_enabled_for_session(route):
                self.log.debug("host.reply.denied", reason="group_or_llm_disabled")
                return False
            if not await SessionPluginManager.is_plugin_enabled_for_session(
                route, "astrbot_plugin_humanization"
            ):
                self.log.debug("host.reply.denied", reason="plugin_disabled")
                return False
        config = self.context.get_config(umo=event.unified_msg_origin)
        permitted = (
            config["provider_settings"]["enable"]
            and config["agent_runner"]["runner_type"] == "local"
            and await SessionServiceManager.should_process_llm_request(event)
        )
        self.log.debug(
            "host.reply.evaluated",
            permitted=permitted,
            runner=config["agent_runner"]["runner_type"],
            llm_enabled=config["provider_settings"]["enable"],
        )
        return permitted

    async def session_options(self) -> dict[str, str]:
        options = {}
        database = self.context.get_db()
        for row in await database.get_umo_aliases():
            platform, kind, sid = row.umo.split(":", 2)
            options[row.umo] = row.user_alias or row.auto_name or row.umo
            if kind == "GroupMessage":
                prefix = row.creator_sender_id + "_"
                group_id = sid.removeprefix(prefix)
                group_umo = f"{platform}:GroupMessage:{group_id}"
                options[group_umo] = f"群 {group_id}（{platform}）"
        return options

    async def request(self, event):
        """Collect native media and conversation before yielding to the Agent.

        Args:
            event: The event whose native Agent turn has been granted.

        Returns:
            Host request with conversation and media bound.
        """
        cfg = self.context.get_config(umo=event.unified_msg_origin)
        request, _ = await collect_initial_request(
            event,
            self.context,
            MainAgentBuildConfig(
                tool_call_timeout=120,
                streaming_response=False,
                provider_settings=cfg["provider_settings"],
            ),
        )
        return request

    @staticmethod
    def inject_observation(request, context: str, intent: str):
        request.extra_user_content_parts.extend(
            [
                TextPart(text=context).mark_as_temp(),
                TextPart(text="本轮表达意图：" + intent).mark_as_temp(),
            ]
        )

    async def generate(self, provider: str, system: str, prompt: str) -> str:
        started = time.monotonic()
        self.log.debug(
            "model.request", provider=provider, system_prompt=system, prompt=prompt
        )
        response = await self.context.llm_generate(
            chat_provider_id=provider, system_prompt=system, prompt=prompt
        )
        self.log.debug(
            "model.response",
            provider=provider,
            text=response.completion_text,
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
        return response.completion_text
