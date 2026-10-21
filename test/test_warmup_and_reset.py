"""Recorder observation thresholds and administrator reset lifecycle contracts."""

import asyncio
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from diary_helpers import topic_change
from humanization_test.core.astrbot_adapter import IdleEvent
from humanization_test.core.settings import Settings
from humanization_test.main import Humanization
from humanization_test.models.decision import Decision
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin
from test_management import admin_event
from test_management import managed as managed
from test_scheduling import Clock

from astrbot.api import AstrBotConfig
from astrbot.api.star import StarTools
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.star.session_llm_manager import SessionServiceManager
from astrbot.core.star.star_handler import EventType, star_handlers_registry


@pytest.mark.parametrize("mode", ["probability", "scheduled"])
async def test_default_fifty_rows_block_all_reply_paths_until_threshold(managed, mode):
    managed.settings.recorder["minimum_context_enabled"] = True
    managed.settings.controller["mode"] = mode
    managed.controller.decide = AsyncMock(return_value=Decision(False))
    managed.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="hello"))
    queue = asyncio.Queue()
    managed.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    managed.scheduler.clock = clock
    managed.scheduler.call_later = clock.later
    for number in range(1, 50):
        event = Event(direct=True, message_id=str(number))
        await consume(managed.observe(event))
        assert event.call_llm and event.get_extra("humanization_claimed")
        assert await consume(managed.participate(event)) == []
    managed.controller.decide.assert_not_awaited()
    managed.adapter.request.assert_not_awaited()
    assert not managed.scheduler.states and queue.empty()

    event = Event(direct=True, message_id="50")
    await consume(managed.observe(event))
    scope = event.get_extra("humanization_message").scope
    session = await managed.storage.session(scope)
    idle = IdleEvent(managed.context, event.platform_meta, session, managed.generation)
    # Idle also uses this guard, independently of its timing policy.
    managed.settings.recorder["minimum_context_messages"] = 51
    assert await consume(managed.turn(idle, idle=True)) == []
    managed.controller.decide.assert_not_awaited()
    managed.settings.recorder["minimum_context_messages"] = 50

    assert await consume(managed.participate(event)) == []
    if mode == "scheduled":
        clock.advance(0)
        await consume(managed.observe(queue.get_nowait()))
    managed.controller.decide.assert_awaited_once()
    # Reaching the threshold permits assessment; a wait decision sends nothing.
    managed.adapter.request.assert_not_awaited()


async def test_threshold_counts_retained_recorder_rows_not_a_lifetime_counter(managed):
    managed.settings.recorder.update(
        minimum_context_enabled=True, minimum_context_messages=3
    )
    event = Event(message_id="first")
    await consume(managed.observe(event))
    message = event.get_extra("humanization_message")
    await consume(managed.observe(Event("/ignored", message_id="command")))
    await consume(managed.observe(Event(message_id="first")))
    assert not await managed.ready_context(message.scope)
    # Sent bubbles are Recorder rows, so they count under the requested DB rule.
    await managed.storage.append(replace(message, message_id="sent", direction="out"))
    assert not await managed.ready_context(message.scope)
    await consume(managed.observe(Event(message_id="third")))
    assert await managed.ready_context(message.scope)
    assert not await managed.ready_context(message.scope, through_seq=2)
    assert await managed.ready_context(message.scope, through_seq=3)

    managed.storage.retention = 2
    await managed.storage.trim()
    state = await managed.storage.session(message.scope)
    assert state["last_seq"] == 3 and state["human_count"] == 2
    assert not await managed.ready_context(message.scope)
    # Even a cumulative counter greater than the threshold cannot grant entry.
    await consume(managed.observe(Event(message_id="fourth")))
    assert (await managed.storage.session(message.scope))["human_count"] == 3
    assert not await managed.ready_context(message.scope)
    managed.settings.recorder["minimum_context_enabled"] = False
    assert await managed.ready_context(message.scope)


async def test_warmup_shares_group_rows_and_exempts_private_chats(managed):
    managed.settings.recorder.update(
        minimum_context_enabled=True, minimum_context_messages=2
    )
    for sender in ("42", "43"):
        event = admin_event("chat", sender=sender)
        event.session.session_id = sender + "_123"
        event.message_obj.message_id = sender
        await consume(managed.observe(event))
    group = event.get_extra("humanization_message")
    assert await managed.ready_context(group.scope)
    private = admin_event("chat", private=True)
    managed.settings.scope["manual_sessions"].append(private.unified_msg_origin)
    await consume(managed.observe(private))
    assert await managed.ready_context(private.get_extra("humanization_message").scope)
    await managed.reset_scope(group, None)
    assert not await managed.ready_context(group.scope)
    fresh = Event(message_id="fresh")
    await consume(managed.observe(fresh))
    assert not await managed.ready_context(group.scope)


@pytest.mark.parametrize("mode", ["probability", "scheduled"])
async def test_private_reply_reaches_main_model_below_group_threshold(managed, mode):
    managed.settings.recorder["minimum_context_enabled"] = True
    managed.settings.scope["all_sessions"] = True
    managed.settings.controller["mode"] = mode
    managed.controller.decide = AsyncMock(return_value=Decision(True, "reply"))
    managed.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="hello"))
    queue = asyncio.Queue()
    managed.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    managed.scheduler.clock = clock
    managed.scheduler.call_later = clock.later
    event = admin_event("hello", private=True)
    event.role = "member"
    await consume(managed.observe(event))
    message = event.get_extra("humanization_message")
    assert len(await managed.storage.recent(message.scope, 100)) == 1
    assert managed.settings.recorder["minimum_context_messages"] == 50

    if mode == "scheduled":
        assert await consume(managed.participate(event)) == []
        clock.advance(60)
        generator = managed.observe(queue.get_nowait())
    else:
        generator = managed.participate(event)
    try:
        assert isinstance(await anext(generator), ProviderRequest)
        managed.controller.decide.assert_awaited_once()
        managed.adapter.request.assert_awaited_once()
    finally:
        await generator.aclose()

    group = Event(message_id="group-first")
    await consume(managed.observe(group))
    assert await consume(managed.participate(group)) == []
    managed.controller.decide.assert_awaited_once()
    managed.adapter.request.assert_awaited_once()


@pytest.mark.parametrize("count", [0, -1, True, 1.5, 501])
def test_minimum_count_must_be_an_integer_within_retention(config, count):
    config["recorder"]["minimum_context_messages"] = count
    with pytest.raises(ValueError, match="Minimum context"):
        Settings(config)


async def test_native_llm_off_preserves_recording_and_independent_summary(
    managed, monkeypatch
):
    monkeypatch.setattr(
        SessionServiceManager,
        "should_process_llm_request",
        AsyncMock(return_value=False),
    )
    managed.settings.recorder.update(summary_provider="summary", summary_every=1)
    managed.summarizer.generate = AsyncMock(return_value="observed diary")
    managed.controller.decide = AsyncMock()
    managed.adapter.request = AsyncMock()
    event = Event(direct=True)
    await consume(managed.observe(event))
    assert not event.get_extra("humanization_claimed")
    assert await consume(managed.participate(event)) == []
    assert len(await managed.storage.rows("SELECT * FROM messages")) == 1
    await managed.summarizer.tick()
    managed.summarizer.generate.assert_awaited_once()
    managed.controller.decide.assert_not_awaited()
    managed.adapter.request.assert_not_awaited()


@pytest.mark.parametrize("mode", ["all", "today"])
@pytest.mark.parametrize("target", ["123", "43_123"])
async def test_private_target_reset_preserves_caller_and_other_chats(
    managed, mode, target
):
    group_event = admin_event("group")
    caller = admin_event("private", private=True)
    other = admin_event("other", group="456")
    for event in (group_event, caller, other):
        await managed.storage.append(managed.adapter.snapshot(event))
    group = managed.adapter.snapshot(group_event)
    today = datetime.now(managed.settings.timezone).date()
    for day in ((today - timedelta(days=1)).isoformat(), today.isoformat()):
        await managed.storage.commit_summary(
            group.scope, day, [topic_change(day)], 1, 1, time.time()
        )
    manager = managed.context.conversation_manager
    manager.get_conversations.return_value = [
        SimpleNamespace(user_id="onebot:GroupMessage:43_123"),
        SimpleNamespace(user_id="onebot:GroupMessage:42_456"),
    ]
    umo = f"onebot:GroupMessage:{target}"
    warning = await managed.admin.request_reset(caller, mode, umo)
    assert umo in warning and "{target}" not in warning
    assert len(await managed.storage.rows("SELECT * FROM messages")) == 3
    wrong_chat = admin_event("/hum IClearKnowWhatIDoingNow")
    assert "没有" in await managed.admin.confirm(wrong_chat)
    confirm = admin_event("/hum IClearKnowWhatIDoingNow", private=True)
    assert await managed.admin.confirm(confirm) == "done"
    assert not await managed.storage.recent(group.scope, 10)
    assert await managed.storage.recent(managed.adapter.snapshot(caller).scope, 10)
    assert await managed.storage.recent(managed.adapter.snapshot(other).scope, 10)
    assert [row["day"] for row in await managed.storage.diaries(group.scope)] == (
        [(today - timedelta(days=1)).isoformat()] if mode == "today" else []
    )
    routes = {call.args[0] for call in manager.new_conversation.call_args_list}
    assert routes == {"onebot:GroupMessage:123", "onebot:GroupMessage:43_123"}


@pytest.mark.parametrize(
    "target", ["bad", "onebot:OtherMessage:1", "onebot:GroupMessage:789"]
)
async def test_invalid_target_cancels_previous_request_without_deletion(
    managed, target
):
    caller = admin_event("request", private=True)
    await managed.storage.append(managed.adapter.snapshot(caller))
    await managed.admin.request_reset(caller, "all")
    old = next(iter(managed.admin.pending.values()))
    response = await managed.admin.request_reset(caller, "all", target)
    assert "60" not in response and old["timer"].cancelled()
    assert not managed.admin.pending
    assert len(await managed.storage.rows("SELECT * FROM messages")) == 1


async def test_target_reset_is_private_only_and_uses_official_command_parser(managed):
    await managed.storage.append(managed.adapter.snapshot(Event()))
    assert "私聊" in await managed.admin.request_reset(
        admin_event("request"), "all", "onebot:GroupMessage:123"
    )
    assert not managed.admin.pending
    event = admin_event("hum reset_data all onebot:GroupMessage:123", private=True)
    event.is_at_or_wake_command = True
    handler = next(
        entry
        for entry in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent
        )
        if entry.handler_module_path == "humanization_test.main"
        and entry.handler_name == "reset_data"
    )
    assert all(rule.filter(event, {}) for rule in handler.event_filters)
    instance = Humanization.__new__(Humanization)
    instance.runtime = managed
    results = await consume(
        instance.reset_data(event, **event.get_extra("parsed_params"))
    )
    assert len(results) == 1
    assert "onebot:GroupMessage:123" in results[0].get_plain_text()


async def test_reset_all_cancels_pending_and_active_work_in_disabled_scopes(managed):
    managed.settings.controller["mode"] = "scheduled"
    queue = asyncio.Queue()
    managed.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    managed.scheduler.clock = clock
    managed.scheduler.call_later = clock.later
    event = Event(direct=True)
    await consume(managed.observe(event))
    await consume(managed.participate(event))
    clock.advance(0)
    stale = queue.get_nowait()
    group = managed.adapter.snapshot(event)
    private = managed.adapter.snapshot(admin_event("private", private=True))
    await managed.storage.append(private)
    await managed.storage.commit_summary(
        group.scope, group.day, [topic_change("diary")], 1, 1, time.time()
    )
    await managed.storage.start_reply(group.scope, time.time(), "message")
    # Disabling the scope does not protect its existing data from an explicit wipe.
    managed.settings.scope["sessions"] = []
    await managed.admin.request_reset(admin_event("request", private=True), "all")
    managed.settings.recorder.update(summary_provider="summary", summary_every=1)
    managed.settings.scope["all_sessions"] = True
    started = asyncio.Event()

    async def blocked_summary(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    managed.summarizer.generate = blocked_summary
    old = asyncio.create_task(managed.summary_loop())
    managed.summary_task = old
    managed.tasks.add(old)
    await started.wait()
    managed.settings.scope["all_sessions"] = False
    assert await managed.reset_all() == 2
    assert old.cancelled() and managed.summary_task is not old
    assert not managed.resetting_all and not managed.scheduler.states
    assert not managed.admin.pending
    for table in ("sessions", "messages", "diary_days", "diary_topics", "reply_runs"):
        assert not await managed.storage.rows(f"SELECT * FROM {table}")
    assert await consume(managed.observe(stale)) == [] and stale.is_stopped()
    assert managed.storage.path.exists()
    assert {
        call.args[0]
        for call in managed.context.conversation_manager.new_conversation.call_args_list
    } == {group.umo, private.umo}


async def test_pre_reset_observation_waiting_on_lock_cannot_restore_old_rows(managed):
    original = Event()
    await consume(managed.observe(original))
    message = original.get_extra("humanization_message")
    lock = managed.record_locks[message.scope]
    await lock.acquire()
    captured = asyncio.Event()
    snapshot = managed.adapter.snapshot

    def inspected(event):
        result = snapshot(event)
        captured.set()
        return result

    managed.adapter.snapshot = inspected
    reset = asyncio.create_task(managed.reset_scope(message, None))
    await asyncio.sleep(0)
    stale = Event(message_id="waiting")
    waiting = asyncio.create_task(consume(managed.observe(stale)))
    await captured.wait()
    lock.release()
    await reset
    await waiting
    assert not await managed.storage.rows("SELECT * FROM messages")
    assert stale.call_llm


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("global_reset", [False, True])
async def test_retained_diaries_remain_addressable_after_today_reset(
    managed, private, global_reset
):
    event = admin_event("old background", private=private)
    message = managed.adapter.snapshot(event)
    await managed.storage.append(message)
    yesterday = (
        datetime.now(managed.settings.timezone).date() - timedelta(days=1)
    ).isoformat()
    await managed.storage.commit_summary(
        message.scope, yesterday, [topic_change("older")], 1, 1, time.time()
    )
    await managed.reset_scope(message, message.day)
    assert not await managed.storage.rows("SELECT * FROM sessions")
    assert await managed.storage.diaries(message.scope)
    if global_reset:
        assert await managed.reset_all() == 1
    else:
        caller = admin_event("request", private=True)
        assert "60" in await managed.admin.request_reset(caller, "all", message.umo)
        assert (
            await managed.admin.confirm(
                admin_event("/hum IClearKnowWhatIDoingNow", private=True)
            )
            == "done"
        )
    assert not await managed.storage.diaries(message.scope)
    assert managed.context.conversation_manager.new_conversation.await_count == 2


async def test_reset_all_cancels_running_reply_and_releases_turn_cache(managed):
    source = Event(direct=True)
    managed.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="hello"))
    await consume(managed.observe(source))
    started = asyncio.Event()

    async def reply():
        generator = managed.participate(source)
        try:
            await anext(generator)
            started.set()
            await asyncio.Event().wait()
        finally:
            await generator.aclose()

    task = asyncio.create_task(reply())
    await started.wait()
    await managed.reset_all()
    assert task.cancelled() and source.get_extra("humanization_turn") is None
    assert not managed.active_scopes and not managed.active
    assert not await managed.storage.rows("SELECT * FROM reply_runs")


async def test_failed_reset_all_releases_pause_and_reports_failure(managed):
    await managed.storage.append(managed.adapter.snapshot(Event()))
    managed.context.conversation_manager.new_conversation.side_effect = OSError()
    with pytest.raises(OSError):
        await managed.reset_all()
    assert not managed.resetting_all and not managed.summarizer.resetting
    assert len(await managed.storage.rows("SELECT * FROM messages")) == 1
    await managed.log.flush()
    events = [
        json.loads(line)["event"]
        for line in (managed.log.directory / "runtime.log")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert "admin.reset_all.failed" in events


async def test_plugin_load_never_triggers_data_reset(tmp_path, monkeypatch):
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "_conf_schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "danger" not in schema
    config = AstrBotConfig(str(tmp_path / "config.json"), schema=schema)
    monkeypatch.setattr(StarTools, "get_data_dir", lambda: tmp_path)
    context = SimpleNamespace(
        persona_manager=SimpleNamespace(get_persona=AsyncMock()),
        get_db=lambda: SimpleNamespace(get_umo_aliases=AsyncMock(return_value=[])),
        register_web_api=Mock(),
        registered_web_apis=[],
    )
    instance = Humanization(context, config)
    instance.runtime.reset_all = AsyncMock()
    await instance.initialize()
    try:
        instance.runtime.reset_all.assert_not_awaited()
    finally:
        await instance.terminate()
