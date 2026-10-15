"""Local-time participation configuration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityPeriod:
    start: int
    end: int
    group: float
    private: float
