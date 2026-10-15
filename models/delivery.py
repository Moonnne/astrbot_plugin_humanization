"""Native replay result retaining prepared message components."""

from dataclasses import dataclass, field

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
