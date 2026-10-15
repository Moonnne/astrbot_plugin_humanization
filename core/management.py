"""Administrator commands with sender-bound, expiring reset confirmations."""

import asyncio
import time
from dataclasses import replace
from datetime import datetime

from astrbot.api.event import filter
from astrbot.api.message_components import Plain
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType


class ManagementMessageFilter(filter.CustomFilter):
    def filter(self, event, cfg) -> bool:
        text = "".join(p.text for p in event.get_messages() if isinstance(p, Plain))
        words = text.split()
        normalized = event.message_str.split()
        return bool(
            (words and words[0] == "/hum")
            or (event.is_at_or_wake_command and normalized and normalized[0] == "hum")
        )


class ManagementAccessFilter(filter.CustomFilter):
    settings = None

    def filter(self, event, cfg) -> bool:
        settings = type(self).settings
        return bool(settings and settings.management["enabled"] and event.is_admin())


class Management:
    confirmation = "IClearKnowWhatIDoingNow"
    all_confirmation = "CLEAR_ALL_HUMANIZATION_DATA"

    def __init__(self, runtime):
        self.runtime = runtime
        self.pending = {}

    def allowed(self, event) -> bool:
        return (
            not self.runtime.closed
            and self.runtime.settings.management["enabled"]
            and event.is_admin()
        )

    async def clear_log(self, event, target: str) -> str:
        if not self.allowed(event):
            return ""
        if not event.is_private_chat():
            return "此指令仅允许在私聊中使用"
        if target not in ("log", "dev_log"):
            return "未知的指令参数\n用法：/hum clear log 或 /hum clear dev_log"
        name = "runtime.log" if target == "log" else "dev.log"
        try:
            await self.runtime.log.clear(name)
        except OSError as exc:
            self.runtime.log.console.error(
                "Humanization admin log clear failed: %s (%s)", name, type(exc).__name__
            )
            return f"error: {type(exc).__name__}"
        self.runtime.log.console.info("Humanization admin cleared %s", name)
        return "done"

    async def info(self, event, umo: str = "") -> str:
        """Inspect Recorder metadata without recording a command or invoking models.

        Args:
            event: Administrator's command event, providing the default scope.
            umo: Optional group or private route; group member routes share records.

        Returns:
            A named, six-line status report or an input/empty-scope explanation.
        """
        if not self.allowed(event):
            return ""
        if event.get_platform_name() != "aiocqhttp":
            return "当前插件的聊天数据查询仅支持 OneBot 会话"
        message = self.runtime.adapter.snapshot(event)
        try:
            route = MessageSession.from_str(umo or message.umo)
        except ValueError:
            return "UMO 格式错误，应为 [平台实例]:GroupMessage:[群号] 或 [平台实例]:FriendMessage:[用户号]；请替换为实际值，不输入方括号，可用 /sid 查看实际 UMO"
        if (
            not route.platform_id
            or not route.session_id
            or route.message_type
            not in (MessageType.GROUP_MESSAGE, MessageType.FRIEND_MESSAGE)
        ):
            return "仅支持有效的 OneBot 群聊或私聊 UMO"
        private = route.message_type == MessageType.FRIEND_MESSAGE
        sid = route.session_id if private else route.session_id.rsplit("_", 1)[-1]
        scope = message.scope if not umo else None
        if umo:
            for target in await self.runtime.storage.reset_targets():
                if target.platform != route.platform_id or target.private != private:
                    continue
                if (private and target.umo == umo) or (
                    not private and target.group_id == sid
                ):
                    scope = target.scope
                    break
        query_umo = f"{route.platform_id}:{route.message_type.value}:{sid}"
        aliases = await self.runtime.context.get_db().get_umo_aliases()
        matching = [
            row
            for row in aliases
            if row.umo == query_umo
            or (
                not private
                and row.umo.startswith(f"{route.platform_id}:GroupMessage:")
                and row.umo.split(":", 2)[2].endswith("_" + sid)
            )
        ]
        matching.sort(key=lambda row: row.umo != query_umo)
        name = next(
            (
                row.user_alias or row.auto_name
                for row in matching
                if row.user_alias or row.auto_name
            ),
            f"{'用户' if private else '群'} {sid}",
        )
        heading = (
            f"[{'私聊' if private else '群聊'}]{' '.join(name.split())} : {query_umo}"
        )
        data = {"message_count": 0, "diary_count": 0, "pending_count": 0}
        diary = []
        if scope is not None:
            # Hold only the DB write lock; a model call never owns this lock.
            async with self.runtime.storage.lock:
                data = (
                    await self.runtime.storage.rows(
                        "SELECT (SELECT COUNT(*) FROM messages WHERE scope=?) AS message_count,"
                        "(SELECT COUNT(DISTINCT day) FROM diary_topics WHERE scope=?) AS diary_count,"
                        "COALESCE((SELECT human_count-summarized_count FROM sessions WHERE scope=?),0) AS pending_count",
                        (scope, scope, scope),
                    )
                )[0]
                diary = await self.runtime.storage.rows(
                    "SELECT day,through_seq,updated_at FROM diary_days d WHERE scope=? AND EXISTS "
                    "(SELECT 1 FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day) "
                    "ORDER BY day DESC LIMIT 1",
                    (scope,),
                )
        settings = self.runtime.settings
        now = datetime.now(settings.timezone).strftime("%Y-%m-%d %H:%M:%S %z")
        if not data["message_count"] and not data["diary_count"]:
            enabled = settings.recorder["enabled"] and settings.selected(
                str(route), query_umo
            )
            status = (
                ("指定会话无记录" if umo else "当前会话无记录")
                if enabled
                else "会话未启用插件"
            )
            return f"{heading}\n{status}\n查询时间：{now}"
        version = "暂无日记"
        if diary:
            current = diary[0]
            created = datetime.fromtimestamp(
                current["updated_at"], settings.timezone
            ).strftime("%Y-%m-%d %H:%M:%S %z")
            version = f"{current['day']}@seq{current['through_seq']}（版本生成时间：{created}）"
        models = []
        for provider_id in (
            settings.recorder["summary_provider"],
            settings.controller["gate_provider"],
        ):
            if not provider_id:
                models.append("未配置")
                continue
            provider = self.runtime.context.get_provider_by_id(provider_id)
            models.append(
                f"{provider.get_model() or '模型名未指定'}（{provider_id}）"
                if provider
                else f"不可用（{provider_id}）"
            )
        return "\n".join(
            (
                heading,
                f"会话数据条目: MAX {settings.recorder['retention']} / NOW {data['message_count']}",
                f"日记版本: {version}; 日记总数: {data['diary_count']}; 摘要进度: TAR {settings.recorder['summary_every']} / NOW {data['pending_count']}",
                f"Recorder 模型: {models[0]}",
                f"Controller 模型: {models[1]}",
                f"查询时间: {now}",
            )
        )

    async def request_reset(self, event, mode: str, umo: str = "") -> str:
        """Bind a reset to its requester while resolving an optional private-chat target.

        Args:
            event: Administrator's original command event.
            mode: Whether to remove all diaries or only the request-date diary.
            umo: Optional native route; group member routes target the whole group.

        Returns:
            A confirmation warning or a validation error, without deleting data.
        """
        if not self.allowed(event):
            return ""
        if event.get_platform_name() != "aiocqhttp":
            return "当前插件的聊天数据重置仅支持 OneBot 会话"
        message = self.runtime.adapter.snapshot(event)
        key = (message.umo, message.self_id, str(event.get_sender_id()))
        previous = self.pending.pop(key, None)
        if previous:
            previous["timer"].cancel()
        if mode not in ("all", "today"):
            return "未知的指令参数\n用法：/hum reset_data all [UMO] 或 /hum reset_data today [UMO]\n[UMO] 为可选参数，填写时替换为实际 UMO，不输入方括号"
        targets = [message]
        if umo:
            if not event.is_private_chat():
                return "指定 UMO 的数据重置仅允许管理员在私聊中发起"
            try:
                route = MessageSession.from_str(umo)
            except ValueError:
                return "UMO 格式错误，应为 [平台实例]:GroupMessage:[群号] 或 [平台实例]:FriendMessage:[用户号]；方括号内为占位符，填写时替换为实际值，不输入方括号。可用 /sid 查看实际 UMO"
            if (
                not route.platform_id
                or not route.session_id
                or route.message_type
                not in (MessageType.GROUP_MESSAGE, MessageType.FRIEND_MESSAGE)
            ):
                return "仅支持有效的 OneBot 群聊或私聊 UMO"
            targets = [
                replace(target, umo=umo)
                for target in await self.runtime.storage.reset_targets()
                if target.platform == route.platform_id
                and (
                    (
                        route.message_type == MessageType.FRIEND_MESSAGE
                        and target.private
                        and target.umo == umo
                    )
                    or (
                        route.message_type == MessageType.GROUP_MESSAGE
                        and not target.private
                        and (
                            route.session_id == target.group_id
                            or route.session_id.endswith("_" + target.group_id)
                        )
                    )
                )
            ]
            if not targets:
                return "该 UMO 没有可定位的 Humanization 会话数据，未创建重置请求。请用 /sid 核对实际 UMO，勿直接输入 [平台实例] 等占位符"
        entry = {
            "mode": mode,
            "day": datetime.now(self.runtime.settings.timezone).date().isoformat(),
            "expires": time.monotonic() + 60,
            "targets": targets,
        }

        def expire():
            self.pending.pop(key, None)

        entry["timer"] = asyncio.get_running_loop().call_later(60, expire)
        self.pending[key] = entry
        target = (
            f"指定会话 {umo}（{'群聊' if not targets[0].private else '私聊'}）"
            if umo
            else "当前群聊"
            if not message.private
            else "当前私聊"
        )
        diaries = "全部日记" if mode == "all" else f"{entry['day']} 的日记"
        return (
            f"⚠️危险操作警告："
            f"当前命令将清空 {target} 的全部原始聊天、回复记录和 {diaries}，重置进度与计数器，并切换到空白对话。\n"
            f"如果真的希望执行本操作，请 60 秒内在当前会话中输入 /hum {self.confirmation} 确认操作"
        )

    async def confirm(self, event) -> str:
        if not self.allowed(event):
            return ""
        if event.message_str.split() not in (
            ["hum", self.confirmation],
            ["/hum", self.confirmation],
        ):
            return f"请完整输入 /hum {self.confirmation}"
        key = (
            event.unified_msg_origin,
            str(event.get_self_id()),
            str(event.get_sender_id()),
        )
        entry = self.pending.pop(key, None)
        if not entry:
            return "没有待确认重置请求，或请求已超时"
        entry["timer"].cancel()
        if time.monotonic() >= entry["expires"]:
            return "确认已超时，重置操作取消"
        try:
            for target in entry["targets"]:
                await self.runtime.reset_scope(
                    target, entry["day"] if entry["mode"] == "today" else None
                )
        except Exception as exc:
            self.runtime.log.exception("admin.reset.failed", mode=entry["mode"])
            self.runtime.log.console.error(
                "Humanization admin data reset failed (%s)", type(exc).__name__
            )
            return f"error: {type(exc).__name__}"
        self.runtime.log.console.info(
            "Humanization admin reset %s data for conversation %s",
            entry["mode"],
            ",".join(
                self.runtime.log.identity(target.scope) for target in entry["targets"]
            ),
        )
        return "done"

    def close(self):
        for entry in self.pending.values():
            entry["timer"].cancel()
        self.pending.clear()
