"""Detached attachment capture result."""

from dataclasses import dataclass


@dataclass
class Resource:
    id: str
    kind: str
    name: str
    path: str = ""
    size: int = 0
    source: str = ""
    description: str = ""
    status: str = "skipped"
