"""Integration with AstrBot's native request collector and event interfaces."""

import asyncio
import copy
import json
import re
import time
import uuid
from collections import OrderedDict
from datetime import datetime

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Plain, Poke, Reply
from astrbot.core.agent.context.token_counter import EstimateTokenCounter
from astrbot.core.agent.message import Message as AgentMessage
from astrbot.core.agent.message import TextPart
from astrbot.core.astr_main_agent import MainAgentBuildConfig, collect_initial_request
from astrbot.core.pipeline.process_stage.follow_up import _ACTIVE_AGENT_RUNNERS
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.provider.entities import TokenUsage
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.filter.regex import RegexFilter
from astrbot.core.star.session_llm_manager import SessionServiceManager
from astrbot.core.star.session_plugin_manager import SessionPluginManager

from ..models.message import Message


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
        return settings.scope_action(event.unified_msg_origin, group_umo) != "ignore"


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
        self.on_cleanup = None
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

    def cleanup_temporary_local_files(self):
        super().cleanup_temporary_local_files()
        if self.on_cleanup is not None:
            callback, self.on_cleanup = self.on_cleanup, None
            callback()


class ScheduledEvent(AiocqhttpMessageEvent):
    """Retain a real OneBot input for delayed native Agent processing."""

    def __init__(self, source, message, generation):
        """Keep adapter capabilities while transferring temporary-file ownership.

        Args:
            source: Real OneBot event after native preprocessing and other handlers.
            message: Stored incoming message used for the pending batch.
            generation: Runtime identifier that rejects events after reload.
        """
        # Re-enter WakingCheck with raw text so wake prefixes are stripped only once.
        super().__init__(
            source.message_obj.message_str,
            copy.deepcopy(source.message_obj),
            source.platform_meta,
            source.session_id,
            getattr(source, "bot", None),
        )
        self.source = source
        self.role = source.role
        self.on_cleanup = None
        self.set_extra("humanization_message", message)
        self.set_extra("humanization_scheduled", {"generation": generation})
        for key in (
            "selected_provider",
            "selected_model",
            "_api_key_allow_admin_role",
            "_current_platform_message_history_id",
        ):
            value = source.get_extra(key)
            if value is not None:
                self.set_extra(key, value)
        for path in list(source._temporary_local_files):
            source.untrack_temporary_local_file(path)
            self.track_temporary_local_file(path)

    async def send(self, message):
        await self.source.send(message)
        self._has_send_oper = True

    async def send_typing(self):
        await self.source.send_typing()

    async def stop_typing(self):
        await self.source.stop_typing()

    def cleanup_temporary_local_files(self):
        super().cleanup_temporary_local_files()
        if self.on_cleanup is not None:
            callback, self.on_cleanup = self.on_cleanup, None
            callback()
        self.get_extra("humanization_scheduled").pop("ticket", None)
        self.source = None


class InternalEventFilter(filter.CustomFilter):
    def filter(self, event, cfg) -> bool:
        return bool(
            event.get_extra("humanization_scheduled")
            or event.get_extra("humanization_idle")
        )


class AstrBotAdapter:
    def __init__(self, context, settings, log):
        self.context = context
        self.settings = settings
        self.log = log
        self.robot_cache = OrderedDict()
        self.robot_slots = asyncio.Semaphore(4)
        self.group_names = {}
        self.group_names_lock = asyncio.Lock()

    async def is_group_robot(self, event, sender_id: str) -> bool:
        """Resolve a group sender using bounded, short-lived platform metadata.

        Args:
            event: Event providing the platform, bot account and group route.
            sender_id: Sender to classify, including a quoted/history sender.

        Returns:
            True only for an explicit boolean is_robot result. Unknown senders
            remain visible; failures are cached briefly to avoid retry storms.
        """
        if (
            not self.settings.recorder["filter_group_robots"]
            or event.is_private_chat()
            or not sender_id
        ):
            return False
        return await self._group_robot(
            event.get_platform_id(),
            str(event.get_self_id()),
            str(event.get_group_id()),
            str(sender_id),
            getattr(event, "bot", None),
        )

    async def is_robot_record(self, row: dict) -> bool:
        """Exclude identified incoming bot records when reading existing rows."""
        if (
            not self.settings.recorder["filter_group_robots"]
            or row["private"]
            or row["direction"] != "in"
        ):
            return False
        return await self._group_robot(
            row["platform"], row["self_id"], row["group_id"], row["sender_id"]
        )

    async def _group_robot(self, platform_id, self_id, group_id, sender_id, bot=None):
        """Share bounded member lookups between events and stored observations.

        Args:
            platform_id: Host adapter instance identifier.
            self_id: Receiving bot account, also used for OneBot routing.
            group_id: Group containing the sender.
            sender_id: Member to classify.
            bot: Current event's client, or None to resolve it from the host.

        Returns:
            Whether the platform explicitly identifies the member as a robot.
        """
        key = (platform_id, self_id, group_id, sender_id)
        async with self.robot_slots:
            cached = self.robot_cache.get(key)
            if cached and cached[0] > time.monotonic():
                self.robot_cache.move_to_end(key)
                return cached[1] is True
            value = None
            try:
                if bot is None:
                    platform = self.context.get_platform_inst(platform_id)
                    bot = platform.get_client() if platform else None
                if bot is not None:
                    async with asyncio.timeout(3):
                        result = await bot.call_action(
                            "get_group_member_info",
                            self_id=self_id,
                            group_id=int(group_id),
                            user_id=int(sender_id),
                        )
                    if type(result.get("is_robot")) is bool:
                        value = result["is_robot"]
            except Exception as exc:
                self.log.debug(
                    "member.robot.lookup_failed", error_type=type(exc).__name__
                )
            self.robot_cache[key] = (
                time.monotonic() + (600 if value is not None else 30),
                value,
            )
            self.robot_cache.move_to_end(key)
            if len(self.robot_cache) > 2048:
                self.robot_cache.popitem(last=False)
            return value is True

    async def filter_group_robot(self, event) -> bool:
        """Exclude bot input without stopping native persistence or commands."""
        if event.get_extra("humanization_filtered_robot"):
            return True
        if not await self.is_group_robot(event, str(event.get_sender_id())):
            return False
        event.set_extra("humanization_filtered_robot", True)
        self.suppress_native_llm(event)
        self.log.debug(
            "message.filtered", reason="group_robot", sender_id=event.get_sender_id()
        )
        return True

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
            elif isinstance(part, Poke):
                raw = event.message_obj.raw_message
                notice = (
                    isinstance(raw, dict)
                    and raw.get("post_type") == "notice"
                    and raw.get("sub_type") == "poke"
                )
                # Only notification target_id identifies a user. A normal poke
                # message segment's id can instead identify a poke animation.
                target = str(raw.get("target_id") or "") if notice else ""
                target = target if target.isdecimal() and int(target) > 0 else None
                actor = str(event.get_sender_id())
                directed = target == str(event.get_self_id()) if target else None
                segments.append(
                    {
                        "type": "poke",
                        "sender_id": actor,
                        "target_id": target,
                        "target_is_self": directed,
                    }
                )
                relation = (
                    ("目标是本机器人" if directed else "目标不是本机器人")
                    if target
                    else "目标未知，不推定为本机器人"
                )
                rendered.append(
                    f"[poke：发送者QQ={actor}；目标QQ={target or '未知'}；{relation}]"
                )
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

    def scope_action(self, event) -> str:
        """Resolve an event's ordinary-message policy using its shared group route.

        Args:
            event: A OneBot group or private message event.

        Returns:
            The configured route action, without applying command exemptions.
        """
        group = str(event.get_group_id() or "")
        route = (
            f"{event.get_platform_id()}:GroupMessage:{group}"
            if group
            else event.unified_msg_origin
        )
        return self.settings.scope_action(event.unified_msg_origin, route)

    @staticmethod
    def is_plugin_command(event) -> bool:
        """Recognize commands already matched by AstrBot, without guessing prefixes.

        Args:
            event: Event after native handler matching.

        Returns:
            Whether a matched handler is a command, command group or regex command.
        """
        handlers = event.get_extra("activated_handlers") or []
        return any(
            isinstance(f, (CommandFilter, CommandGroupFilter, RegexFilter))
            for handler in handlers
            for f in handler.event_filters
        )

    def is_command(self, event) -> bool:
        if self.is_plugin_command(event):
            return True
        # WakingCheck may have stripped a wake prefix from message_str.
        raw = "".join(
            p.text for p in event.get_messages() if isinstance(p, Plain)
        ).lstrip()
        return self.settings.is_command_text(raw)

    @staticmethod
    def suppress_native_llm(event):
        """Disable native model triggers while preserving command handlers and storage.

        Args:
            event: Current event with its mutable activated handler list.
        """
        event.should_call_llm(True)
        handlers = event.get_extra("activated_handlers")
        if handlers:
            handlers[:] = [
                handler
                for handler in handlers
                if not (
                    handler.handler_module_path == "astrbot.builtin_stars.astrbot.main"
                    and handler.handler_name in {"handle_empty_mention", "on_message"}
                )
            ]

    @staticmethod
    def suppress_empty_mention(event):
        """Keep controlled input out of the host's separate empty-mention Agent."""
        handlers = event.get_extra("activated_handlers")
        if handlers:
            # Mutate the current event's list before its next handler executes.
            # Do not change the registry, native message recorder or command waiters.
            handlers[:] = [
                handler
                for handler in handlers
                if not (
                    handler.handler_module_path == "astrbot.builtin_stars.astrbot.main"
                    and handler.handler_name == "handle_empty_mention"
                )
            ]

    def filter_command_quote(self, event, request):
        """Remove command quotations from this turn's additional input.

        Args:
            event: Incoming non-command event supplying any quoted message.
            request: Native request retaining its original conversation history.
        """
        if not self.settings.recorder["filter_commands"]:
            return
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

    async def filter_agent_history(self, event, run_context):
        """Keep filtered input outside inference and native compression.

        Args:
            event: Event owning this plugin's current Agent turn.
            run_context: Native context assembled before its first model call.
        """
        turn = event.get_extra("humanization_turn")
        if not turn:
            return
        # Read the native per-UMO runner only for counters; never replace it.
        runner = _ACTIVE_AGENT_RUNNERS.get(event.unified_msg_origin)
        if runner is not None:
            turn["usage_runner"] = runner
            turn["usage_previous"] = TokenUsage()
        filter_commands = self.settings.recorder["filter_commands"]
        filter_robots = (
            self.settings.recorder["filter_group_robots"]
            and not event.is_private_chat()
        )
        if not filter_commands and not filter_robots:
            return
        original = run_context.messages
        retained = []
        removed = set()
        replacements = {}
        excluded = False
        for message in original:
            if message.role == "user":
                content = message.content or ""
                text = (
                    content
                    if isinstance(content, str)
                    else "\n".join(
                        part.text for part in content if isinstance(part, TextPart)
                    )
                )
                excluded = filter_commands and self.settings.is_command_text(text)
                if filter_robots and not excluded:
                    # Match the host's identity reminder, never nicknames or a
                    # user merely mentioning another account in ordinary text.
                    sender = re.search(
                        r"<system_reminder>User ID: (\d+), Nickname:", text
                    )
                    if sender:
                        excluded = await self.is_group_robot(event, sender.group(1))
            if excluded:
                removed.add(id(message))
            else:
                filtered = message
                if filter_robots and message.role == "user":
                    # Native group context is a nickname-only aggregate. Use the
                    # filtered plugin observation rather than guessing authors.
                    header = (
                        "<system_reminder>You are in a group chat. "
                        "Belows are group chat context after your last reply:\n"
                        "--- BEGIN CONTEXT---\n"
                    )
                    pattern = (
                        re.escape(header)
                        + r".*?\n--- END CONTEXT ---\n</system_reminder>"
                    )
                    if isinstance(message.content, str):
                        content = re.sub(pattern, "", message.content, flags=re.DOTALL)
                    else:
                        content = []
                        for part in message.content or []:
                            if isinstance(part, TextPart):
                                text = re.sub(pattern, "", part.text, flags=re.DOTALL)
                                if text != part.text:
                                    if text:
                                        content.append(
                                            part.model_copy(update={"text": text})
                                        )
                                    continue
                            content.append(part)
                    if content != message.content:
                        filtered = message.model_copy(
                            update={"content": content or "[群聊观察见本轮资料]"}
                        )
                        replacements[id(filtered)] = message
                retained.append(filtered)
        if removed or replacements:
            turn["command_history"] = (original, removed, replacements)
            run_context.messages = retained
        self.log.debug(
            "context.input.filtered",
            removed_history_items=len(removed),
            replaced_items=len(replacements),
        )

    def restore_agent_history(self, event, run_context):
        """Restore excluded rounds before the native history writer runs.

        Args:
            event: Event owning the temporary command-history references.
            run_context: Finished native context, possibly compressed or truncated.
        """
        turn = event.get_extra("humanization_turn")
        saved = turn.pop("command_history", None) if turn else None
        if saved is None:
            return
        original, removed, replacements = saved
        messages = [
            replacements.get(id(message), message) for message in run_context.messages
        ]
        positions = {id(message): index for index, message in enumerate(messages)}
        insertions = {}
        position = len(messages)
        # Dropped normal rounds stay dropped; command rounds precede the next
        # surviving original message, even when older anchors were compressed.
        for message in reversed(original):
            identity = id(message)
            if identity in positions:
                position = positions[identity]
            elif identity in removed:
                insertions.setdefault(position, []).append(message)
        restored = []
        for index in range(len(messages) + 1):
            restored.extend(reversed(insertions.get(index, [])))
            if index < len(messages):
                restored.append(messages[index])
        run_context.messages = restored
        self.log.debug(
            "context.input.restored",
            restored_history_items=len(removed),
            restored_items=len(replacements),
        )

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

    async def session_options(self, resolve_groups: bool = False) -> dict[str, str]:
        database = self.context.get_db()
        rows = await database.get_umo_aliases()
        options = {row.umo: row.user_alias or row.auto_name or row.umo for row in rows}
        groups = {}
        for row in rows:
            platform, kind, sid = row.umo.split(":", 2)
            if kind == "GroupMessage":
                prefix = row.creator_sender_id + "_"
                group_id = sid.removeprefix(prefix)
                group_umo = f"{platform}:GroupMessage:{group_id}"
                groups[group_umo] = (
                    row.user_alias or row.auto_name or groups.get(group_umo) or group_id
                )
        # Preserve exact-route aliases; isolated member routes also name the group.
        for umo, name in groups.items():
            if options.get(umo, umo) == umo:
                options[umo] = name
        if resolve_groups:
            for umo in (
                self.settings.scope["sessions"]
                + self.settings.scope["manual_sessions"]
                + self.settings.scope["blacklist_sessions"]
                + self.settings.scope["blacklist_manual_sessions"]
            ):
                parts = umo.split(":", 2)
                if len(parts) == 3 and parts[1] == "GroupMessage":
                    platform, _, sid = parts
                    group_id = sid.rsplit("_", 1)[-1]
                    groups.setdefault(f"{platform}:GroupMessage:{group_id}", group_id)
            for umo, name in groups.items():
                options.setdefault(umo, name)
            aliases = {row.umo: row.user_alias for row in rows}
            for platform in {umo.split(":", 1)[0] for umo in groups}:
                names = await self._group_names(platform)
                for umo in groups:
                    instance, _, group_id = umo.split(":", 2)
                    if instance == platform and group_id in names:
                        options[umo] = aliases.get(umo) or names[group_id]
        return options

    async def _group_names(self, platform_id: str) -> dict[str, str]:
        """Read OneBot group names once per instance, with a ten-minute cache."""
        async with self.group_names_lock:
            cached = self.group_names.get(platform_id)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            platform = self.context.get_platform_inst(platform_id)
            if platform is None or platform.meta().name != "aiocqhttp":
                return {}
            try:
                async with asyncio.timeout(3):
                    groups = await platform.get_client().call_action("get_group_list")
                names = {
                    str(group["group_id"]): group["group_name"]
                    for group in groups
                    if group.get("group_name")
                }
                self.group_names[platform_id] = (time.monotonic() + 600, names)
            except Exception as exc:
                names = cached[1] if cached else {}
                self.group_names[platform_id] = (time.monotonic() + 60, names)
                self.log.debug(
                    "scope.names.unavailable",
                    platform=platform_id,
                    error=type(exc).__name__,
                )
            return names

    async def request(self, event):
        """Collect native media and conversation before yielding to the Agent.

        Args:
            event: The event whose native Agent turn has been granted.

        Returns:
            Host request with conversation and media bound.
        """
        # Remove confirmed bot quotations before native media extraction, and
        # retain the filtered event through Agent construction. Turn cleanup
        # restores the original object; native incoming persistence ran earlier.
        turn = event.get_extra("humanization_turn")
        if turn is not None and self.settings.recorder["filter_group_robots"]:
            parts = []
            for part in event.get_messages():
                if isinstance(part, Reply) and await self.is_group_robot(
                    event, str(part.sender_id or "")
                ):
                    continue
                parts.append(part)
            if len(parts) != len(event.get_messages()):
                turn["robot_quote_message"] = event.message_obj
                event.message_obj = copy.copy(event.message_obj)
                event.message_obj.message = parts
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
        if request is None:
            return None
        if any(isinstance(part, Poke) for part in event.get_messages()):
            description = self.snapshot(event).text
            if not request.prompt:
                request.prompt = description
            else:
                request.extra_user_content_parts.append(
                    TextPart(text="本轮事件：" + description)
                )
        if not request.prompt and not (
            request.image_urls or request.audio_urls or request.extra_user_content_parts
        ):
            # The native builder rejects empty input before request hooks run.
            # Preserve a bare mention/wake prefix without inventing a question.
            request.prompt = self.snapshot(event).text
        return request

    @staticmethod
    def inject_observation(
        request, context: str, intent: str, planning=None, focus=None
    ):
        guidance = "本轮表达意图：" + intent
        if planning is not None:
            # Only collapse exact duplicates in this request, never infer identity
            # from native history text or discard an out-of-window focus snapshot.
            if focus and focus.get("message"):
                message = focus["message"]
                if message["message_id"] and message in json.loads(context)["messages"]:
                    focus = {
                        **focus,
                        "message": {"message_id": message["message_id"]},
                    }
            guidance = "本轮聊天规划（尚未执行，焦点仅表示语义对象）：" + json.dumps(
                {
                    "emotion": planning["emotion"],
                    "plan": planning["plan"],
                    "focus": focus,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        request.extra_user_content_parts.extend(
            [
                TextPart(text=context).mark_as_temp(),
                TextPart(text=guidance).mark_as_temp(),
            ]
        )

    async def generate(
        self, provider: str, system: str, prompt: str, purpose: str = "auxiliary"
    ) -> str:
        started = time.monotonic()
        estimate = EstimateTokenCounter().count_tokens(
            [
                AgentMessage(role="system", content=system),
                AgentMessage(role="user", content=prompt),
            ]
        )
        self.log.debug(
            "model.request",
            provider=provider,
            purpose=purpose,
            system_prompt=system,
            prompt=prompt,
            estimated_input=estimate,
        )
        try:
            response = await self.context.llm_generate(
                chat_provider_id=provider, system_prompt=system, prompt=prompt
            )
        except (Exception, asyncio.CancelledError) as exc:
            self.record_model_usage(
                purpose,
                provider,
                estimate,
                None,
                None,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                status="cancelled"
                if isinstance(exc, asyncio.CancelledError)
                else "error",
                error_type=type(exc).__name__,
            )
            raise
        self.record_model_usage(
            purpose,
            provider,
            estimate,
            response.usage,
            response,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            status="error" if response.role == "err" else "ok",
        )
        self.log.debug(
            "model.response",
            provider=provider,
            text=response.completion_text,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            usage={
                "input": response.usage.input,
                "input_cached": response.usage.input_cached,
                "output": response.usage.output,
                "total": response.usage.total,
            }
            if response.usage is not None
            else None,
        )
        return response.completion_text

    def record_model_usage(
        self, purpose, provider, estimate, usage, response, **fields
    ):
        """Record available provider counters without copying model contents.

        Args:
            purpose: Controller, Recorder, format repair or main-model role.
            provider: Configured provider identifier.
            estimate: Heuristic estimate of the supplied message content.
            usage: Native TokenUsage, or None when unavailable.
            response: Model response supplying optional raw usage counters.
            **fields: Call status, duration and accounting scope.
        """
        raw = response.raw_completion if response is not None else None
        raw_usage = (
            raw.get("usage") if isinstance(raw, dict) else getattr(raw, "usage", None)
        )
        if raw_usage is not None and not isinstance(raw_usage, dict):
            raw_usage = raw_usage.model_dump()
        details = {}
        if raw_usage:
            for source, target in (
                ("prompt_tokens", "input"),
                ("input_tokens", "input"),
                ("completion_tokens", "output"),
                ("output_tokens", "output"),
                ("total_tokens", "total"),
                ("prompt_cache_hit_tokens", "cache_read"),
                ("prompt_cache_miss_tokens", "cache_miss"),
                ("cache_read_input_tokens", "cache_read"),
                ("cache_creation_input_tokens", "cache_write"),
            ):
                if source in raw_usage:
                    details[target] = raw_usage[source]
            input_details = (
                raw_usage.get("prompt_tokens_details")
                or raw_usage.get("input_tokens_details")
                or {}
            )
            if "cached_tokens" in input_details:
                details["cache_read"] = input_details["cached_tokens"]
            output_details = (
                raw_usage.get("completion_tokens_details")
                or raw_usage.get("output_tokens_details")
                or {}
            )
            if "reasoning_tokens" in output_details:
                details["reasoning"] = output_details["reasoning_tokens"]
        cached = details.get(
            "cache_read", usage.input_cached if usage is not None else None
        )
        fields.setdefault("scope", "call")
        self.log.model_usage(
            purpose=purpose,
            provider=provider,
            estimated_input=estimate,
            usage={
                "input": usage.input,
                "input_cached": cached,
                "output": usage.output,
                "total": usage.total,
            }
            if usage is not None
            else None,
            provider_details=details or None,
            cache_source="provider"
            if "cache_read" in details
            else "native"
            if usage is not None
            else None,
            cache_ratio=cached / usage.input
            if usage is not None and usage.input and cached is not None
            else None,
            response_id=response.id if response is not None else None,
            **fields,
        )

    def record_main_usage(self, event):
        """Consume native cumulative counters once per observable Agent step.

        Args:
            event: Event whose tool or completion hook has finished a model step.
        """
        turn = event.get_extra("humanization_turn")
        if not turn or "usage_runner" not in turn:
            return
        runner = turn["usage_runner"]
        stats = runner.stats
        if not stats.end_time or turn.get("usage_time") == stats.end_time:
            return
        usage = stats.token_usage - turn["usage_previous"]
        turn["usage_previous"] = stats.token_usage
        turn["usage_time"] = stats.end_time
        messages = runner.run_context.messages
        estimate = EstimateTokenCounter().count_tokens(
            messages[:-1] if messages and messages[-1].role == "assistant" else messages
        )
        response = runner.get_final_llm_resp()
        self.record_model_usage(
            "main",
            runner.provider.provider_config.get("id", ""),
            estimate,
            usage if usage.total or (response and response.usage is not None) else None,
            response,
            scope="native_step",
            run=turn["run"],
            status="cancelled"
            if runner.was_aborted()
            else "error"
            if response and response.role == "err"
            else "ok",
        )
