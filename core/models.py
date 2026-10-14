"""Host-independent records passed between runtime modules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    scope: str
    umo: str
    platform: str
    self_id: str
    group_id: str
    sender_id: str
    sender_name: str
    message_id: str
    sent_at: float
    received_at: float
    text: str
    segments: str
    private: bool
    day: str
    direction: str = "in"


@dataclass(frozen=True)
class Decision:
    reply: bool
    intent: str = ""
    reason: str = ""
