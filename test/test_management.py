"""Management permissions, confirmation identity, log barriers and scoped resets."""

import asyncio
import copy
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from humanization_test.main import Humanization
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.core.config.default import DEFAULT_CONFIG
from astrbot.core.pipeline.context_utils import call_handler
from astrbot.core.pipeline.respond.stage import RespondStage
from astrbot.core.pipeline.waking_check.stage import WakingCheckStage
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.star.session_plugin_manager import SessionPluginManager
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType, star_handlers_registry


def admin_event(text, sender="42", private=False, group="123"):
    event = Event(text, sender=sender)
    event.role = "admin"
    kind = MessageType.FRIEND_MESSAGE if private else MessageType.GROUP_MESSAGE
    event.message_obj.type = kind
    event.message_obj.group_id = "" if private else group
    event.session = MessageSession("onebot", kind, sender if private else group)
    return event


@pytest.fixture
def managed(plugin):
    plugin.settings.management["enabled"] = True
    plugin.log.console = Mock()
    plugin.context.conversation_manager = SimpleNamespace(
        get_conversations=AsyncMock(return_value=[]),
        get_curr_conversation_id=AsyncMock(return_value="old"),
        get_conversation=AsyncMock(return_value=SimpleNamespace(persona_id="mutsumi")),
        new_conversation=AsyncMock(return_value="new"),
    )
    return plugin


@pytest.mark.parametrize("debug", [False, True])
async def test_log_clear_discards_queued_records_and_cannot_restore_them(
    managed, debug
):
    managed.log.debug_mode = debug
    name = "dev.log" if debug else "runtime.log"
    managed.log.info("old.pending")
    event = admin_event(
        "/hum clear dev_log" if debug else "/hum clear log", private=True
    )
    assert await managed.admin.clear_log(event, "dev_log" if debug else "log") == "done"
    path = managed.log.directory / name
    assert path.read_bytes() == b""
    managed.log.info("new.after_clear")
    await managed.log.flush()
    assert [
        json.loads(line)["event"]
        for line in path.read_text(encoding="utf-8").splitlines()
    ] == ["new.after_clear"]
    managed.log.console.info.assert_called_once()


async def test_log_clear_permission_and_private_chat_restrictions(managed):
    event = admin_event("/hum clear log", private=True)
    event.role = "member"
    managed.log.clear = AsyncMock()
    assert await managed.admin.clear_log(event, "log") == ""
    event.role = "admin"
    managed.settings.management["enabled"] = False
    assert await managed.admin.clear_log(event, "log") == ""
    managed.settings.management["enabled"] = True
    assert "私聊" in await managed.admin.clear_log(admin_event("/hum clear log"), "log")
    managed.log.clear.assert_not_awaited()


async def test_clear_reports_io_error_to_console_and_administrator(managed):
    managed.log.clear = AsyncMock(side_effect=PermissionError("private path"))
    result = await managed.admin.clear_log(
        admin_event("/hum clear log", private=True), "log"
    )
    assert result == "error: PermissionError"
    managed.log.console.error.assert_called_once()


@pytest.mark.parametrize("command", ["clear", "claer"])
async def test_official_command_parser_accepts_log_command_and_requested_alias(
    managed, command
):
    event = admin_event(f"hum {command} dev_log", private=True)
    event.is_at_or_wake_command = True
    handler = next(
        entry
        for entry in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent
        )
        if entry.handler_module_path == "humanization_test.main"
        and entry.handler_name == "clear_log"
    )
    assert all(rule.filter(event, {}) for rule in handler.event_filters)
    instance = Humanization.__new__(Humanization)
    instance.runtime = managed
    await instance.management_guard(event)
    results = await consume(
        instance.clear_log(event, **event.get_extra("parsed_params"))
    )
    assert len(results) == 1 and results[0].get_plain_text() == "done"
    managed.settings.recorder["filter_commands"] = False
    await consume(managed.observe(event))
    assert not await managed.storage.rows("SELECT * FROM messages")


async def test_confirmation_requires_same_admin_chat_exact_text_and_deadline(managed):
    request = admin_event("/hum reset_data all")
    managed.reset_scope = AsyncMock()
    assert "60" in await managed.admin.request_reset(request, "all")
    confirm = "/hum IClearKnowWhatIDoingNow"
    assert "没有" in await managed.admin.confirm(admin_event(confirm, sender="43"))
    assert "没有" in await managed.admin.confirm(admin_event(confirm, group="456"))
    assert "完整" in await managed.admin.confirm(admin_event(confirm + " extra"))
    managed.reset_scope.assert_not_awaited()
    assert await managed.admin.confirm(admin_event(confirm)) == "done"
    managed.reset_scope.assert_awaited_once()
    assert "没有" in await managed.admin.confirm(admin_event(confirm))
    await managed.admin.request_reset(request, "today")
    entry = next(iter(managed.admin.pending.values()))
    entry["expires"] = time.monotonic() - 1
    assert "超时" in await managed.admin.confirm(admin_event(confirm))
    assert managed.reset_scope.await_count == 1
    await managed.admin.request_reset(request, "all")
    entry = next(iter(managed.admin.pending.values()))
    entry["timer"]._callback()
    assert not managed.admin.pending
    entry["timer"].cancel()


@pytest.mark.parametrize("mode", ["all", "today"])
async def test_scoped_reset_clears_counters_and_preserves_other_chats(managed, mode):
    source = Event()
    await consume(managed.observe(source))
    message = source.get_extra("humanization_message")
    other = replace(message, scope="other", message_id="other")
    await managed.storage.append(other)
    today = datetime.now(managed.settings.timezone).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    await managed.storage.commit_summary(
        message.scope, yesterday, "older", 1, 1, time.time()
    )
    await managed.storage.commit_summary(
        message.scope, today.isoformat(), "today", 1, 1, time.time()
    )
    await managed.storage.commit_summary(
        other.scope, today.isoformat(), "other", 1, 1, time.time()
    )
    await managed.storage.start_reply(message.scope, time.time(), "message")
    await managed.storage.start_reply(other.scope, time.time(), "message")
    await managed.reset_scope(message, today.isoformat() if mode == "today" else None)
    assert not await managed.storage.recent(message.scope, 100)
    assert await managed.storage.recent(other.scope, 100)
    assert not await managed.storage.rows(
        "SELECT * FROM sessions WHERE scope=?", (message.scope,)
    )
    assert not await managed.storage.rows(
        "SELECT * FROM reply_runs WHERE scope=?", (message.scope,)
    )
    assert await managed.storage.rows(
        "SELECT * FROM reply_runs WHERE scope=?", (other.scope,)
    )
    diaries = await managed.storage.diaries(message.scope)
    assert [row["body"] for row in diaries] == (["older"] if mode == "today" else [])
    manager = managed.context.conversation_manager
    assert manager.new_conversation.await_count == 1
    assert manager.new_conversation.call_args.kwargs["persona_id"] == "mutsumi"
    new = Event(message_id="fresh")
    await consume(managed.observe(new))
    state = await managed.storage.session(message.scope)
    assert state["last_seq"] == 1 and state["human_count"] == 1
    assert state["cursor"] == state["summarized_count"] == state["idle_count"] == 0


async def test_reset_switches_all_isolated_group_routes_and_preserves_other_routes(
    managed,
):
    source = Event()
    await consume(managed.observe(source))
    manager = managed.context.conversation_manager
    manager.get_conversations.return_value = [
        SimpleNamespace(user_id=route)
        for route in (
            "onebot:GroupMessage:42_123",
            "onebot:GroupMessage:43_123",
            "onebot:GroupMessage:42_456",
            "onebot:FriendMessage:42",
        )
    ]
    await managed.reset_scope(source.get_extra("humanization_message"), None)
    assert {call.args[0] for call in manager.new_conversation.call_args_list} == {
        "onebot:GroupMessage:123",
        "onebot:GroupMessage:42_123",
        "onebot:GroupMessage:43_123",
    }


async def test_reset_cancels_old_reply_and_rejects_stale_event(managed):
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
    await managed.reset_scope(source.get_extra("humanization_message"), None)
    assert task.cancelled()
    assert source.get_extra("humanization_turn") is None
    assert not managed.active_scopes
    assert await consume(managed.participate(source)) == []
    assert not await managed.storage.rows("SELECT * FROM reply_runs")


async def test_reset_cancels_pending_summary_without_restoring_diary(managed):
    source = Event()
    await consume(managed.observe(source))
    managed.settings.recorder.update(summary_provider="summary", summary_every=1)
    started = asyncio.Event()

    async def generate(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    managed.summarizer.generate = generate
    old = asyncio.create_task(managed.summary_loop())
    managed.summary_task = old
    managed.tasks.add(old)
    await started.wait()
    await managed.reset_scope(source.get_extra("humanization_message"), None)
    assert old.cancelled()
    assert not await managed.storage.rows("SELECT * FROM daily_summaries")
    assert managed.summary_task is not old


@pytest.mark.parametrize(
    "text",
    [
        "/hum",
        "/hum clear",
        "/hum reset_data wrong",
        "/hum IClearKnowWhatIDoingNow",
        "/hum unknown",
    ],
)
@pytest.mark.parametrize("enabled, admin", [(False, True), (True, False)])
async def test_native_waking_and_handlers_remain_silent_for_denied_commands(
    managed, monkeypatch, text, enabled, admin
):
    managed.settings.management["enabled"] = enabled
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["admins_id"] = ["42"] if admin else []
    config["wake_prefix"] = ["/"]
    stage = WakingCheckStage()
    await stage.initialize(
        SimpleNamespace(
            astrbot_config=config, db_helper=Mock(), astrbot_config_id="test"
        )
    )
    stage._umo_auto_name_recorder = SimpleNamespace(schedule=Mock())
    registry = star_handlers_registry.get_handlers_by_event_type(
        EventType.AdapterMessageEvent
    )
    handlers = [
        item
        for item in registry
        if item.handler_module_path == "humanization_test.main"
    ]
    monkeypatch.setattr(
        star_handlers_registry,
        "get_handlers_by_event_type",
        lambda kind, **kwargs: (
            handlers if kind == EventType.AdapterMessageEvent else []
        ),
    )
    monkeypatch.setitem(
        star_map, "humanization_test.main", SimpleNamespace(name="Humanization")
    )
    monkeypatch.setattr(
        SessionPluginManager,
        "filter_handlers_by_session",
        AsyncMock(side_effect=lambda event, items: items),
    )
    event = Event(text)
    await stage.process(event)
    respond = RespondStage()
    await respond.initialize(SimpleNamespace(astrbot_config=config))
    instance = Humanization.__new__(Humanization)
    instance.runtime = managed
    for handler in event.get_extra("activated_handlers", []):
        params = event.get_extra("handlers_parsed_params", {}).get(
            handler.handler_full_name, {}
        )
        async for _ in call_handler(
            event, getattr(instance, handler.handler_name), **params
        ):
            stopped = event.is_stopped()
            await respond.process(event)
            if stopped:
                break
        if stopped:
            break
    assert stopped and event.call_llm
    assert event.sent == []
    assert not await managed.storage.rows("SELECT * FROM messages")
