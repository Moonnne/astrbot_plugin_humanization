import asyncio
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from diary_helpers import model_change, topic_change
from humanization_test.core.controller.controller import Controller
from humanization_test.core.models import Message
from humanization_test.core.recorder.storage import Storage
from humanization_test.core.recorder.summarizer import Summarizer
from humanization_test.core.settings import Settings
from humanization_test.utils.output_protocol import OutputProtocol


def message(index, scope="group", day="2026-10-13"):
    return Message(
        scope,
        "onebot:GroupMessage:123",
        "onebot",
        "999",
        "123",
        "42",
        "User",
        str(index),
        float(index),
        float(index),
        f"message {index}",
        "[]",
        False,
        day,
    )


@pytest.fixture
async def storage(tmp_path):
    store = Storage(tmp_path / "chat.sqlite3", 5)
    await store.open()
    yield store
    await store.close()


def test_default_is_opt_in(config):
    settings = Settings(config)
    assert settings.controller["mode"] == "scheduled"
    assert settings.controller["force_at"] is True
    assert settings.recorder["minimum_context_enabled"] is True
    assert settings.recorder["minimum_context_messages"] == 50
    assert not settings.selected("onebot:GroupMessage:123", "onebot:GroupMessage:123")
    config["scope"]["sessions"] = ["onebot:GroupMessage:123"]
    assert settings.selected("onebot:GroupMessage:42_123", "onebot:GroupMessage:123")
    assert not settings.selected("other:GroupMessage:123", "other:GroupMessage:123")


def test_cross_midnight_period_and_edges(config):
    config["controller"]["periods"] = [
        {"start": "23:00", "end": "08:00", "group": 0, "private": 0.4}
    ]
    settings = Settings(config)

    def at(hour):
        return datetime(2026, 10, 13, hour, tzinfo=settings.timezone)

    assert settings.activity(False, at(23)) == 0
    assert settings.activity(True, at(1)) == 0.4
    assert settings.activity(False, at(8)) == 0.2


def test_overlapping_periods_rejected(config):
    config["controller"]["periods"] = [
        {"start": "23:00", "end": "08:00", "group": 0, "private": 0},
        {"start": "07:00", "end": "09:00", "group": 1, "private": 1},
    ]
    with pytest.raises(ValueError, match="overlap"):
        Settings(config)


def test_invalid_summary_window_rejected(config):
    config["recorder"]["summary_every"] = config["recorder"]["window"] + 1
    with pytest.raises(ValueError, match="summary_every"):
        Settings(config)


@pytest.mark.parametrize("key", ["runtime_max_mb", "dev_max_mb"])
@pytest.mark.parametrize("limit", [-1, float("inf"), float("nan"), "5", True])
def test_invalid_log_size_limit_rejected(config, key, limit):
    config["logging"][key] = limit
    with pytest.raises(ValueError, match="non-negative"):
        Settings(config)


@pytest.mark.parametrize("limit", [0, 0.5, 5])
def test_nonnegative_log_size_limits_are_valid(config, limit):
    config["logging"].update(runtime_max_mb=limit, dev_max_mb=limit)
    Settings(config)


@pytest.mark.parametrize(
    "text",
    ["a$$b", "$a", "a$", "a\nb", "a\\nb", "**hello**", "（点头）好", "好😀", "a$b$c$d"],
)
def test_protocol_rejects_ambiguous_output(text):
    with pytest.raises(ValueError):
        OutputProtocol.parse(text)


def test_protocol_normalizes_bubbles():
    assert OutputProtocol.parse(" 没有。 $ 你还好吗？ ") == ["没有", "你还好吗？"]


async def test_retention_per_group_dedup_and_concurrent_append(storage):
    await asyncio.gather(*(storage.append(message(i)) for i in range(10)))
    assert len(await storage.recent("group", 100)) == 5
    assert not await storage.append(message(9))
    await storage.append(message(20, scope="other"))
    assert len(await storage.recent("other", 100)) == 1
    assert (await storage.session("group"))["human_count"] == 10


async def test_retention_change_and_restart(tmp_path):
    path = tmp_path / "db.sqlite3"
    store = Storage(path, 10)
    await store.open()
    for i in range(8):
        await store.append(message(i))
    run = await store.start_reply("group", 1, "message")
    await store.close()
    store = Storage(path, 3)
    await store.open()
    try:
        assert len(await store.recent("group", 99)) == 3
        assert (await store.rows("SELECT status FROM reply_runs WHERE id=?", (run,)))[
            0
        ]["status"] == "unknown"
    finally:
        await store.close()


async def test_outgoing_does_not_count_as_human_activity(storage):
    await storage.append(message(1))
    await storage.update_session("group", idle_waiting=1)
    await storage.append(replace(message(2), direction="out"))
    session = await storage.session("group")
    assert session["human_count"] == 1 and session["last_human"] == 1
    assert session["idle_waiting"] == 1
    await storage.append(message(3))
    assert (await storage.session("group"))["idle_waiting"] == 0


async def test_summary_failure_preserves_cursor_and_records_gap(storage, config, log):
    settings = Settings(config)
    for i in range(8):
        await storage.append(message(i))
    session = await storage.session("group")
    pending = await storage.recent("group", 100)
    generate = AsyncMock(side_effect=TimeoutError)
    worker = Summarizer(storage, settings, generate, "summarize", log)
    with pytest.raises(TimeoutError):
        await worker.summarize(session, pending)
    assert (await storage.session("group"))["cursor"] == 0
    generate.side_effect = None
    generate.return_value = model_change("今天讨论了植物", 4)
    await worker.summarize(session, pending)
    assert (await storage.session("group"))["cursor"] == 8
    assert "覆盖缺口" in (await storage.diaries("group"))[0]["body"]


async def test_sealed_summary_is_immutable(storage):
    await storage.append(message(1))
    await storage.commit_summary(
        "group", "2026-10-12", [topic_change("Yesterday")], 1, 1, 1
    )
    await storage.commit_summary(
        "group", "2026-10-13", [topic_change("Today")], 1, 1, 2
    )
    with pytest.raises(ValueError, match="sealed"):
        await storage.commit_summary(
            "group", "2026-10-12", [topic_change("Changed")], 1, 1, 3
        )
    assert (await storage.diaries("group"))[0]["topics"][0]["topic"] == "Yesterday"


async def test_summary_advances_only_over_input_budget(storage, config, log):
    config["recorder"]["context_chars"] = 400
    settings = Settings(config)
    for i in range(3):
        await storage.append(replace(message(i), text="x" * 300))
    worker = Summarizer(
        storage, settings, AsyncMock(return_value='{"changes":[]}'), "summarize", log
    )
    await worker.summarize(
        await storage.session("group"), await storage.recent("group", 10)
    )
    assert (await storage.session("group"))["cursor"] == 1


async def test_at_bypasses_zero_activity_and_gate(storage, config, log):
    config["controller"]["group"] = 0
    settings = Settings(config)
    await storage.append(message(1))
    generate = AsyncMock()
    control = Controller(settings, storage, generate, None, log)
    assert (await control.decide(message(1), True, False)).reply
    generate.assert_not_called()


async def test_gate_invalid_json_stays_silent(storage, config, log):
    config["controller"].update(group=1, gate_provider="gate")
    await storage.append(message(1))
    prompts = SimpleNamespace(
        gate=AsyncMock(return_value="gate"), context=AsyncMock(return_value="{}")
    )
    control = Controller(
        Settings(config), storage, AsyncMock(return_value="not json"), prompts, log
    )
    assert not (await control.decide(message(1), False, False)).reply


def test_idle_quiet_daily_cap_and_unanswered(config, log):
    config["proactive"]["enabled"] = True
    settings = Settings(config)
    control = Controller(settings, None, None, None, log)
    now = datetime(2026, 10, 13, 12, tzinfo=settings.timezone)
    state = {
        "private": 0,
        "idle_waiting": 0,
        "next_idle": 0,
        "last_human": 0,
        "last_reply": 0,
        "idle_day": "2026-10-13",
        "idle_count": 0,
    }
    assert control.idle_due(state, now)
    assert not control.idle_due(state | {"idle_waiting": 1}, now)
    assert not control.idle_due(state | {"idle_count": 2}, now)
    assert not control.idle_due(state, now.replace(hour=23))
