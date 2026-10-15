"""Detached results that do not retain SQLite cursors."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WriteResult:
    lastrowid: int | None
    rowcount: int
