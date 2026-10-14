"""Administrator commands with sender-bound, expiring reset confirmations."""

import asyncio
import time
from datetime import datetime

from astrbot.api.event import filter
from astrbot.api.message_components import Plain


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
            return "用法：/hum clear log 或 /hum clear dev_log"
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

    async def request_reset(self, event, mode: str) -> str:
        if not self.allowed(event):
            return ""
        if event.get_platform_name() != "aiocqhttp":
            return "当前插件的聊天数据重置仅支持 OneBot 会话"
        if mode not in ("all", "today"):
            return "用法：/hum reset_data all 或 /hum reset_data today"
        message = self.runtime.adapter.snapshot(event)
        key = (message.umo, message.self_id, str(event.get_sender_id()))
        previous = self.pending.pop(key, None)
        if previous:
            previous["timer"].cancel()
        entry = {
            "mode": mode,
            "day": datetime.now(self.runtime.settings.timezone).date().isoformat(),
            "expires": time.monotonic() + 60,
            "message": message,
        }

        def expire():
            self.pending.pop(key, None)

        entry["timer"] = asyncio.get_running_loop().call_later(60, expire)
        self.pending[key] = entry
        target = "本群整体" if not message.private else "当前私聊"
        diaries = (
            "全部日记" if mode == "all" else f"{entry['day']}的日记（保留此前日记）"
        )
        return (
            f"将清空{target}的全部原始聊天、回复记录和{diaries}，重置进度与计数，"
            "并切换到空白 AstrBot 对话（旧对话保留）。"
            f"请本人在同一会话60秒内输入 /hum {self.confirmation} 确认；超时不执行"
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
            return "没有待确认的重置请求，或请求已超过60秒"
        entry["timer"].cancel()
        if time.monotonic() >= entry["expires"]:
            return "确认已超时，未执行重置"
        try:
            await self.runtime.reset_scope(
                entry["message"], entry["day"] if entry["mode"] == "today" else None
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
            self.runtime.log.identity(entry["message"].scope),
        )
        return "done"

    def close(self):
        for entry in self.pending.values():
            entry["timer"].cancel()
        self.pending.clear()
