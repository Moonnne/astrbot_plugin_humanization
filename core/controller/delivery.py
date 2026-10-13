"""Record decorated results after the native sending stage completes."""

import json
import time
from dataclasses import dataclass, field, replace
from datetime import datetime

from astrbot.api.message_components import At, Plain
from astrbot.core.message.message_event_result import MessageEventResult


@dataclass
class ReplayResult(MessageEventResult):
    """Retain native prepared parts when RespondStage extracts separate audio.

    The host removes Record parts from the original chain before its completion
    hook. Observing derive() preserves those parts without replacing transport.
    """

    prepared: list = field(default_factory=list)

    def derive(self, chain=None):
        if chain:
            self.prepared.extend(chain)
        return super().derive(chain)


class Delivery:
    def __init__(self, storage, settings):
        self.storage = storage
        self.settings = settings

    async def record(self, event, turn: dict):
        """Observe native completion once without claiming a transport receipt.

        Args:
            event: Event whose current result has already passed decoration and sending.
            turn: Ephemeral replay state for this invocation.
        """
        index = turn["index"]
        if index in turn["recorded"]:
            return
        rendered = []
        segments = []
        result = event.get_result()
        parts = (
            result.prepared
            if isinstance(result, ReplayResult) and result.prepared
            else result.chain
        )
        for part in parts:
            if isinstance(part, Plain):
                rendered.append(part.text)
                segments.append({"type": "text", "text": part.text})
            elif isinstance(part, At):
                rendered.append(f"[@{part.qq}]")
                segments.append({"type": "at", "id": str(part.qq)})
            else:
                tag = part.type.lower()
                rendered.append(f"[{tag}]")
                segments.append({"type": tag})
        now = time.time()
        day = datetime.fromtimestamp(now, self.settings.timezone).date().isoformat()
        message = turn["message"]
        await self.storage.append(
            replace(
                message,
                sender_id=message.self_id,
                sender_name="Humanization",
                message_id=f"reply:{turn['run']}:{index}",
                sent_at=now,
                received_at=now,
                text="".join(rendered),
                segments=json.dumps(segments, ensure_ascii=False),
                day=day,
                direction="out",
            )
        )
        first = not turn["recorded"]
        turn["recorded"].add(index)
        await self.storage.record_reply_activity(
            message.scope,
            now,
            day,
            event.get_extra("humanization_idle")["last_human"]
            if turn["idle"] and first
            else None,
        )
        if turn["status"] == "not_sent":
            turn["status"] = "processed"
