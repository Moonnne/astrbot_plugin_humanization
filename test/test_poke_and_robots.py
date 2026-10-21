"""OneBot interaction identity and group-robot input boundaries."""

import asyncio
import copy
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiocqhttp import Event as OneBotEvent
from controller_helpers import plan_json
from diary_helpers import model_change
from humanization_test.core.astrbot_adapter import ScheduledEvent
from humanization_test.main import Humanization
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.api.message_components import At, Image, Plain, Poke, Reply
from astrbot.builtin_stars.astrbot.main import Main as NativePlugin
from astrbot.core.agent.message import Message, TextPart
from astrbot.core.config.default import DEFAULT_CONFIG
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter import (
    AiocqhttpAdapter,
)
from astrbot.core.provider.entities import ProviderRequest


@pytest.mark.parametrize("target", [999, 777])
async def test_real_poke_conversion_preserves_target_through_storage_and_request(
    plugin, monkeypatch, target
):
    plugin.settings.controller.update(robot_name="机器人", force_mention=True)
    raw = OneBotEvent(
        {
            "post_type": "notice",
            "notice_type": "notify",
            "sub_type": "poke",
            "self_id": 999,
            "user_id": 42,
            "target_id": target,
            "group_id": 123,
        }
    )
    abm = await AiocqhttpAdapter._convert_handle_notice_event(None, raw)
    event = AiocqhttpMessageEvent("", abm, Event().platform_meta, "123", None)
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    expected = {
        "type": "poke",
        "sender_id": "42",
        "target_id": str(target),
        "target_is_self": target == 999,
    }
    assert json.loads(message.segments) == [expected]
    rows = await plugin.storage.recent(message.scope, 30)
    assert json.loads(rows[0]["segments"]) == [expected]
    for controller in (True, False):
        context = json.loads(
            await plugin.prompts.context(message.scope, for_controller=controller)
        )
        assert context["messages"][0]["text"] == message.text
        assert f"目标QQ={target}" in message.text
    replay = ScheduledEvent(event, message, plugin.generation)
    assert plugin.adapter.snapshot(replay).text == message.text
    assert not any(isinstance(part, At) for part in replay.get_messages())
    plugin.scheduler.submit(event, message, await plugin.storage.session(message.scope))
    state = plugin.scheduler.states[message.scope]
    assert not state.forced
    assert not plugin.settings.mentioned(message.text, message.segments)
    mixed = json.dumps([expected, {"type": "text", "text": "机器人看这里"}])
    assert plugin.settings.mentioned(message.text + "机器人看这里", mixed)
    # Extra reminders must not prevent the current poke from reaching the model.
    request = ProviderRequest(
        extra_user_content_parts=[TextPart(text="native reminder")]
    )
    monkeypatch.setattr(
        "humanization_test.core.astrbot_adapter.collect_initial_request",
        AsyncMock(return_value=(request, None)),
    )
    assert (await plugin.adapter.request(replay)).prompt == message.text
    assert str(abm.message[0].id) == str(target) and abm.raw_message == raw


@pytest.mark.parametrize(
    "raw", [None, {"post_type": "message"}, {"post_type": "notice", "sub_type": "poke"}]
)
async def test_unidentified_poke_never_assumes_component_id_is_target(plugin, raw):
    event = Event("")
    event.message_obj.raw_message = raw
    event.message_obj.message = [Poke(id="999")]
    message = plugin.adapter.snapshot(event)
    part = json.loads(message.segments)[0]
    assert part["target_id"] is None and part["target_is_self"] is None
    assert "目标未知" in message.text


@pytest.mark.parametrize(
    "enabled,robot,private",
    [
        (False, True, False),
        (True, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
async def test_robot_filter_excludes_storage_count_schedule_and_default_reply(
    plugin, enabled, robot, private
):
    plugin.settings.recorder["filter_group_robots"] = enabled
    event = Event(direct=True)
    event.bot = SimpleNamespace(call_action=AsyncMock(return_value={"is_robot": robot}))
    if private:
        event.message_obj.type = MessageType.FRIEND_MESSAGE
        event.message_obj.group_id = ""
    await consume(plugin.observe(event))
    filtered = enabled and robot and not private
    assert bool(event.get_extra("humanization_filtered_robot")) is filtered
    scope = plugin.adapter.snapshot(event).scope
    assert await plugin.storage.message_count(scope) == (0 if filtered else 1)
    if filtered:
        plugin.controller.decide = AsyncMock()
        await consume(plugin.participate(event))
        plugin.controller.decide.assert_not_awaited()
        assert event.call_llm and not event.is_stopped()
        assert not plugin.scheduler.states
        assert await plugin.storage.pending_sessions() == []
    if not enabled or private:
        event.bot.call_action.assert_not_awaited()


async def test_robot_prepare_keeps_native_persistence_and_other_plugins(plugin):
    plugin.settings.recorder["filter_group_robots"] = True
    event = Event(direct=True)
    event.bot = SimpleNamespace(call_action=AsyncMock(return_value={"is_robot": True}))
    handlers = [
        SimpleNamespace(handler_module_path=module, handler_name=name, event_filters=[])
        for module, name in [
            ("astrbot.builtin_stars.astrbot.main", "persist_group_message"),
            ("astrbot.builtin_stars.astrbot.main", "on_message"),
            ("astrbot.builtin_stars.astrbot.main", "handle_empty_mention"),
            ("another.plugin", "on_message"),
        ]
    ]
    event.set_extra("activated_handlers", handlers)
    original = copy.deepcopy(event.message_obj.message)
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    await entry.prepare_input(event)
    await consume(plugin.observe(event))
    assert [h.handler_name for h in handlers] == ["persist_group_message", "on_message"]
    assert handlers[-1].handler_module_path == "another.plugin"
    assert event.message_obj.message == original
    event.bot.call_action.assert_awaited_once()
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["provider_ltm_settings"]["group_message_history_enable"] = True
    history = AsyncMock(return_value=SimpleNamespace(id=1))
    native = object.__new__(NativePlugin)
    native.context = SimpleNamespace(
        get_config=lambda **kw: cfg,
        message_history_manager=SimpleNamespace(insert_message_chain=history),
    )
    await native.persist_group_message(event)
    history.assert_awaited_once()
    assert history.call_args.kwargs["sender_id"] == event.get_sender_id()


@pytest.mark.parametrize(
    "result", [{}, {"is_robot": "true"}, {"is_robot": 1}, TimeoutError()]
)
async def test_unknown_robot_status_is_visible_and_cached_briefly(plugin, result):
    plugin.settings.recorder["filter_group_robots"] = True
    event = Event()
    call = (
        AsyncMock(side_effect=result)
        if isinstance(result, Exception)
        else AsyncMock(return_value=result)
    )
    event.bot = SimpleNamespace(call_action=call)
    assert not await plugin.adapter.is_group_robot(event, "42")
    assert not await plugin.adapter.is_group_robot(event, "42")
    call.assert_awaited_once()
    key = next(iter(plugin.adapter.robot_cache))
    plugin.adapter.robot_cache[key] = (0, None)
    assert not await plugin.adapter.is_group_robot(event, "42")
    assert call.await_count == 2


async def test_robot_cache_separates_group_and_account_and_propagates_cancellation(
    plugin,
):
    plugin.settings.recorder["filter_group_robots"] = True
    event = Event()
    event.bot = SimpleNamespace(call_action=AsyncMock(return_value={"is_robot": True}))
    assert await plugin.adapter.is_group_robot(event, "42")
    event.message_obj.group_id = "456"
    assert await plugin.adapter.is_group_robot(event, "42")
    event.message_obj.self_id = "888"
    assert await plugin.adapter.is_group_robot(event, "42")
    assert event.bot.call_action.await_count == 3
    event.bot.call_action.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await plugin.adapter.is_group_robot(event, "43")
    assert len(plugin.adapter.robot_cache) == 3


async def test_native_group_context_is_temporarily_replaced_not_deleted(plugin):
    plugin.settings.recorder.update(filter_commands=False, filter_group_robots=True)
    event = Event()
    event.set_extra("humanization_turn", {"phase": "agent"})
    header = "<system_reminder>You are in a group chat. Belows are group chat context after your last reply:\n--- BEGIN CONTEXT---\n"
    block = header + "unknown bot content\n--- END CONTEXT ---\n</system_reminder>"
    original = [
        Message(
            role="user",
            content=[
                TextPart(text="human question"),
                TextPart(text=block),
                TextPart(text="filtered plugin observation").mark_as_temp(),
            ],
        )
    ]
    context = SimpleNamespace(messages=original)
    await plugin.adapter.filter_agent_history(event, context)
    assert "unknown bot content" not in str(context.messages)
    assert "human question" in str(context.messages)
    assert "filtered plugin observation" in str(context.messages)
    assert "unknown bot content" in str(original)
    plugin.adapter.restore_agent_history(event, context)
    assert context.messages[0] is original[0]


@pytest.mark.parametrize("cancel", [False, True])
async def test_bot_quote_media_excluded_before_collection_and_restored_after_turn(
    plugin, monkeypatch, cancel
):
    plugin.settings.recorder["filter_group_robots"] = True
    plugin.settings.controller.update(gate_provider="gate")
    event = Event(direct=True)
    event.bot = SimpleNamespace(
        call_action=AsyncMock(
            side_effect=lambda action, **kw: {"is_robot": kw["user_id"] == 777}
        )
    )
    event.message_obj.message.append(
        Reply(
            id="bot-message",
            sender_id="777",
            chain=[
                Plain("bot quote"),
                Image.fromURL("https://example.invalid/never-download.png"),
            ],
        )
    )
    original = event.message_obj
    await consume(plugin.observe(event))
    plugin.controller.generate = AsyncMock(return_value=plan_json())

    async def collect(filtered, *args):
        assert not any(isinstance(p, Reply) for p in filtered.get_messages())
        assert any(isinstance(p, Plain) for p in filtered.get_messages())
        if cancel:
            raise asyncio.CancelledError
        return ProviderRequest(prompt="human question"), None

    monkeypatch.setattr(
        "humanization_test.core.astrbot_adapter.collect_initial_request", collect
    )
    turn = plugin.participate(event)
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await anext(turn)
    else:
        await anext(turn)
        await turn.aclose()
    assert event.message_obj is original
    assert event.get_extra("humanization_turn") is None


@pytest.mark.parametrize("human", [False, True])
async def test_existing_bot_rows_are_filtered_from_observation_and_summary_without_deletion(
    plugin, human
):
    plugin.settings.recorder.update(
        filter_group_robots=True, summary_provider="summary"
    )
    bot = SimpleNamespace(
        call_action=AsyncMock(
            side_effect=lambda action, **kw: {"is_robot": kw["user_id"] == 777}
        )
    )
    plugin.context.get_platform_inst = lambda platform_id: SimpleNamespace(
        get_client=lambda: bot
    )
    base = plugin.adapter.snapshot(Event("human discussion"))
    await plugin.storage.append(
        replace(base, sender_id="777", text="old bot content", message_id="bot")
    )
    if human:
        await plugin.storage.append(base)
    for controller in (True, False):
        observed = await plugin.prompts.context(base.scope, for_controller=controller)
        assert "old bot content" not in observed
        assert ("human discussion" in observed) is human
    worker = plugin.summarizer
    worker.generate = AsyncMock(return_value=model_change("human topic", 2))
    await worker.summarize(
        await plugin.storage.session(base.scope),
        await plugin.storage.pending_messages(base.scope, 0, 20),
    )
    if human:
        payload = json.loads(worker.generate.call_args.args[2])
        assert [row["sender_id"] for row in payload["messages"]] == ["42"]
    else:
        worker.generate.assert_not_awaited()
    assert (await plugin.storage.session(base.scope))["cursor"] == (2 if human else 1)
    assert await plugin.storage.message_count(base.scope) == (2 if human else 1)
