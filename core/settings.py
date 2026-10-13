"""Validated configuration and local-time participation policy."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


def minute_of_day(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"Invalid time: {value}; expected HH:MM")
    return hour * 60 + minute


def in_period(minute: int, start: int, end: int) -> bool:
    if start == end:
        return True
    return start <= minute < end if start < end else minute >= start or minute < end


@dataclass(frozen=True)
class ActivityPeriod:
    start: int
    end: int
    group: float
    private: float


class Settings:
    """Validate user input once, before opening resources or claiming events.

    Args:
        config: AstrBot plugin configuration, populated from the schema.

    Raises:
        ValueError: A range, time period, or dependent setting is invalid.
    """

    def __init__(self, config: dict):
        self.scope = config["scope"]
        self.logging = config["logging"]
        self.recorder = config["recorder"]
        self.controller = config["controller"]
        self.proactive = config["proactive"]
        self.prompts = config["prompts"]
        self.timezone = ZoneInfo(self.controller["timezone"])
        self.periods = [
            ActivityPeriod(
                minute_of_day(p["start"]),
                minute_of_day(p["end"]),
                float(p["group"]),
                float(p["private"]),
            )
            for p in self.controller["periods"]
        ]
        occupied = set()
        for period in self.periods:
            minutes = {m for m in range(1440) if in_period(m, period.start, period.end)}
            if occupied & minutes:
                raise ValueError("Activity periods overlap")
            occupied |= minutes
        probabilities = [
            self.controller[k]
            for k in ("group", "private", "mention_weight", "at_weight")
        ]
        probabilities += [self.proactive["probability"]]
        probabilities += [v for p in self.periods for v in (p.group, p.private)]
        if any(not 0 <= float(v) <= 1 for v in probabilities):
            raise ValueError("Activity and reply weights must be between 0 and 1")
        r = self.recorder
        if not 1 <= r["summary_every"] <= r["window"] <= r["retention"]:
            raise ValueError("Require 1 <= summary_every <= window <= retention")
        if not 1 <= self.controller["context_messages"] <= r["retention"]:
            raise ValueError("Context message count must be within retention")
        for values, keys in (
            (r, ("summary_chars", "context_chars", "summary_timeout")),
            (self.controller, ("gate_timeout",)),
            (
                self.proactive,
                ("idle_minutes", "interval_minutes", "check_minutes", "daily_limit"),
            ),
        ):
            if any(values[key] <= 0 for key in keys):
                raise ValueError(f"Settings must be positive: {keys}")
        if (
            self.controller["cooldown_seconds"] < 0
            or self.controller["debounce_seconds"] < 0
        ):
            raise ValueError("Cooldown and debounce cannot be negative")
        self.quiet_start = minute_of_day(self.proactive["quiet_start"])
        self.quiet_end = minute_of_day(self.proactive["quiet_end"])

    def selected(self, umo: str, group_umo: str) -> bool:
        selected = self.scope["sessions"] + self.scope["manual_sessions"]
        return self.scope["all_sessions"] or umo in selected or group_umo in selected

    def activity(self, private: bool, now: datetime) -> float:
        local = now.astimezone(self.timezone)
        minute = local.hour * 60 + local.minute
        for period in self.periods:
            if in_period(minute, period.start, period.end):
                return period.private if private else period.group
        return float(self.controller["private" if private else "group"])

    def quiet(self, now: datetime) -> bool:
        local = now.astimezone(self.timezone)
        return self.proactive["quiet_enabled"] and in_period(
            local.hour * 60 + local.minute,
            self.quiet_start,
            self.quiet_end,
        )
