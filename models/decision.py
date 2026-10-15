"""Shared data records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    reply: bool
    intent: str = ""
    reason: str = ""
    planning: dict | None = None
    focus: dict | None = None
    record_id: int | None = None
