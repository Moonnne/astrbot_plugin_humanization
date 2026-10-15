"""Shared data records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResetTarget:
    scope: str
    umo: str
    platform: str
    self_id: str
    group_id: str
    private: bool
