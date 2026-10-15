"""Per-conversation scheduling state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.astrbot_adapter import ScheduledEvent


@dataclass
class Ticket:
    scope: str
    epoch: str
    event: ScheduledEvent
    sequence: int
    forced: bool
    direct_at: bool
    mentioned: bool


@dataclass
class ScheduleState:
    epoch: str = field(default_factory=lambda: uuid.uuid4().hex)
    credit: Decimal = Decimal(0)
    idle_credit: Decimal = Decimal(0)
    pending: ScheduledEvent | None = None
    sequence: int = 0
    reviewed: int = 0
    first_at: float = 0
    last_at: float = 0
    last_reply: float = 0
    due: bool = False
    forced: bool = False
    expedited: bool = False
    timer: object = None
    queued: Ticket | None = None
    active: Ticket | None = None
    idle_queued: bool = False
    wait_streak: int = 0
    backoff_until: float = 0
    ready_at: float = 0
