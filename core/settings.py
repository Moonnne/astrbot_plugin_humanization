"""Validated configuration and local-time participation policy."""

import json
import math
import re
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
        self.management = config["management"]
        self.recorder = config["recorder"]
        self.controller = config["controller"]
        self.proactive = config["proactive"]
        self.prompts = config["prompts"]
        if self.controller["mode"] not in ("probability", "scheduled"):
            raise ValueError("Unknown Controller mode")
        if not self.controller["robot_name"].strip():
            raise ValueError("Robot name must not be empty")
        if (
            not 0
            < self.controller["wait_min_seconds"]
            <= self.controller["wait_max_seconds"]
        ):
            raise ValueError("Require 0 < minimum scheduling wait <= maximum wait")
        for key in ("runtime_max_mb", "dev_max_mb"):
            limit = self.logging[key]
            if (
                isinstance(limit, bool)
                or not isinstance(limit, (int, float))
                or not math.isfinite(limit)
                or limit < 0
            ):
                raise ValueError("Log size limits must be finite non-negative numbers")
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
        if (
            not isinstance(r["minimum_context_messages"], int)
            or isinstance(r["minimum_context_messages"], bool)
            or not 1 <= r["minimum_context_messages"] <= r["retention"]
        ):
            raise ValueError(
                "Minimum context count must be an integer within retention"
            )
        for key in ("diary_context_chars", "summary_output_chars"):
            if type(r[key]) is not int or r[key] <= 0:
                raise ValueError(f"{key} must be a positive integer")
        if not 1 <= r["summary_every"] <= r["window"] <= r["retention"]:
            raise ValueError("Require 1 <= summary_every <= window <= retention")
        if not 1 <= self.controller["context_messages"] <= r["retention"]:
            raise ValueError("Context message count must be within retention")
        for values, keys in (
            (r, ("context_chars", "summary_timeout")),
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

    def is_command_text(self, text: str) -> bool:
        return any(
            prefix and text.lstrip().startswith(prefix)
            for prefix in self.recorder["command_prefixes"]
        )

    def is_command_record(self, row: dict) -> bool:
        if not self.recorder["filter_commands"] or row["direction"] != "in":
            return False
        text = "".join(
            part["text"]
            for part in json.loads(row["segments"])
            if part["type"] == "text"
        )
        return self.is_command_text(text)

    def activity(self, private: bool, now: datetime) -> float:
        local = now.astimezone(self.timezone)
        minute = local.hour * 60 + local.minute
        for period in self.periods:
            if in_period(minute, period.start, period.end):
                return period.private if private else period.group
        return float(self.controller["private" if private else "group"])

    def mentioned(self, text: str) -> bool:
        """Recognize configured names without matching inside Latin words.

        Args:
            text: Rendered incoming message content.

        Returns:
            Whether a name or alias appears in the message.
        """
        for value in [self.controller["robot_name"], *self.controller["names"]]:
            name = value.strip()
            if not name:
                continue
            if name.isascii():
                if re.search(
                    r"(?<![a-zA-Z0-9_])" + re.escape(name) + r"(?![a-zA-Z0-9_])",
                    text,
                    re.IGNORECASE,
                ):
                    return True
            elif name in text:
                return True
        return False

    def forced(self, direct_at: bool, mentioned: bool) -> bool:
        return (direct_at and self.controller["force_at"]) or (
            mentioned and self.controller["force_mention"]
        )

    def effective_activity(self, private, direct_at, mentioned, now) -> float:
        activity = self.activity(private, now)
        if direct_at:
            return max(activity, self.controller["at_weight"])
        if mentioned:
            return max(activity, self.controller["mention_weight"])
        return activity

    def frequency_hint(self, activity: float) -> str:
        """Describe nominal evaluation frequency, not a guaranteed reply rate.

        Args:
            activity: Default or period-specific participation value.

        Returns:
            Configuration-page explanation for the selected mode.
        """
        if activity == 0:
            return "积极度0：普通消息不评估、不补偿；已开启的必回复另计。"
        if self.controller["mode"] == "probability":
            return f"当前积极度{activity:g}：每条候选消息约{activity * 100:g}%概率进入门控，实际回复占比通常更低。"
        if activity == 1:
            return "当前积极度1：每条新消息满足额度，通常只等合并窗口；冷却、退避和语义门控仍适用，必回复另计。"
        wait = (
            self.controller["wait_min_seconds"]
            + (
                self.controller["wait_max_seconds"]
                - self.controller["wait_min_seconds"]
            )
            * (1 - activity) ** 2
        )
        return f"当前积极度{activity:g}：普通聊天平均约每{1 / activity:.2f}条新消息评估一次；低流量约{wait:.0f}秒内可补偿。连发合并、冷却和退避可能降低频率，实际发言由门控决定，必回复另计。"

    def quiet(self, now: datetime) -> bool:
        local = now.astimezone(self.timezone)
        return self.proactive["quiet_enabled"] and in_period(
            local.hour * 60 + local.minute,
            self.quiet_start,
            self.quiet_end,
        )
