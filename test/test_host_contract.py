"""Contracts exercised with real AstrBot event, filter and request types."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from humanization_test.core.astrbot_adapter import IdleEvent, ScopeFilter
from humanization_test.core.runtime import Runtime

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import At, Plain
from astrbot.core.message.message_event_result import ResultContentType
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.provider.entities import LLMResponse, ProviderRequest
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.session_llm_manager import SessionServiceManager
from astrbot.core.star.session_plugin_manager import SessionPluginManager


class Event(AstrMessageEvent):
    def __init__(self, text="你好", direct=False, sender="42", message_id="1"):
        message = AstrBotMessage()
        message.type = MessageType.GROUP_MESSAGE
        message.self_id = "999"
        message.group_id = "123"
        message.session_id = "123"
        message.message_id = message_id
        message.sender = MessageMember(user_id=sender, nickname="User")
        message.message = ([At(qq="999")] if direct else []) + [Plain(text)]
        message.message_str = text
        message.timestamp = int(time.time())
        super().__init__(
            text, message, PlatformMetadata("aiocqhttp", "OneBot", "onebot"), "123"
        )
        self.sent = []

    async def send(self, message):
        self.sent.append(message)
        self._has_send_oper = True


@pytest.fixture
async def plugin(config, tmp_path, monkeypatch):
    config["scope"]["sessions"] = ["onebot:GroupMessage:123"]
    config["controller"]["debounce_seconds"] = 0
    monkeypatch.setattr(
        SessionServiceManager,
        "should_process_llm_request",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        SessionServiceManager, "is_session_enabled", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        SessionServiceManager,
        "is_llm_enabled_for_session",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        SessionPluginManager,
        "is_plugin_enabled_for_session",
        AsyncMock(return_value=True),
    )
    context = SimpleNamespace(
        persona_manager=SimpleNamespace(get_persona=AsyncMock()),
        get_config=lambda **kw: {
            "provider_settings": {"enable": True},
            "agent_runner": {"runner_type": "local"},
        },
        get_current_chat_provider_id=AsyncMock(return_value="main"),
    )
    instance = Runtime(context, config, tmp_path)
    await instance.initialize()
    # Background scheduling is tested separately; avoid racing fixture writes.
    for task in instance.tasks:
        task.cancel()
    await asyncio.gather(*instance.tasks, return_exceptions=True)
    yield instance
    await instance.terminate()


async def consume(generator):
    return [item async for item in generator]


async def replay(plugin, event, generator):
    """Drive returned results through a minimal native-send completion contract."""
    async for result in generator:
        event.set_result(result)
        await plugin.defer_result(event)
        if event.get_result():
            await event.send(event.get_result())
            await plugin.after_sent(event)
            event.clear_result()


async def test_scope_filter_does_not_wake_unselected_event(plugin):
    event = Event()
    assert ScopeFilter().filter(event, {})
    event.session.session_id = "other"
    event.unified_msg_origin = "onebot:GroupMessage:other"
    event.message_obj.group_id = "other"
    assert not ScopeFilter().filter(event, {})
    assert not event.is_wake and not event.call_llm


async def test_command_filter_is_default_and_does_not_claim(plugin):
    event = Event("status")
    event.set_extra(
        "activated_handlers", [SimpleNamespace(event_filters=[CommandFilter("status")])]
    )
    await consume(plugin.observe(event))
    assert not event.call_llm
    assert not await plugin.storage.rows("SELECT * FROM messages")


async def test_unregistered_slash_command_is_filtered(plugin):
    await consume(plugin.observe(Event("/unknown")))
    assert not await plugin.storage.rows("SELECT * FROM messages")


async def test_command_recording_can_be_enabled(plugin):
    plugin.settings.recorder["filter_commands"] = False
    event = Event("/status")
    await consume(plugin.observe(event))
    assert len(await plugin.storage.rows("SELECT * FROM messages")) == 1
    assert not event.call_llm


async def test_native_turn_injection_delivery_and_single_owner(plugin):
    event = Event(direct=True)
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    await consume(plugin.observe(event))
    assert event.call_llm
    turn = plugin.participate(event)
    request = await anext(turn)
    scope = event.get_extra("humanization_message").scope
    assert plugin.controller.lock(scope).locked()
    await plugin.inject(event, request)
    assert "$" in request.system_prompt
    assert len(request.extra_user_content_parts) == 2
    assert (
        request.extra_user_content_parts[0].model_dump_for_context()["_no_save"] is True
    )
    response = LLMResponse(role="assistant", completion_text="没有。$你继续")
    await plugin.validate(event, response)
    event.set_result(
        event.plain_result(response.completion_text).set_result_content_type(
            ResultContentType.LLM_RESULT
        )
    )
    await plugin.defer_result(event)
    assert not event.sent
    assert event.get_result() is None
    state = event.get_extra("humanization_turn")
    await replay(plugin, event, turn)
    assert len(event.sent) == 2
    assert state == {} and event.get_extra("humanization_turn") is None
    assert not plugin.controller.lock(scope).locked()
    rows = await plugin.storage.rows("SELECT * FROM reply_runs")
    assert rows[0]["status"] == "processed"
    assert rows[0]["sent_parts"] == 2
    assert (await plugin.storage.session(scope))["human_count"] == 1


async def test_duplicate_input_does_not_schedule_twice(plugin):
    await consume(plugin.observe(Event(direct=True)))
    duplicate = Event(direct=True)
    await consume(plugin.observe(duplicate))
    plugin.adapter.request = AsyncMock()
    assert await consume(plugin.participate(duplicate)) == []
    plugin.adapter.request.assert_not_called()


async def test_other_plugin_response_prevents_our_reply(plugin):
    event = Event(direct=True)
    await consume(plugin.observe(event))
    await event.send(event.plain_result("command response"))
    assert await consume(plugin.participate(event)) == []


async def test_idle_event_is_not_a_human_and_new_message_cancels_it(plugin):
    event = Event()
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    session = await plugin.storage.session(message.scope)
    idle = IdleEvent(plugin.context, event.platform_meta, session, plugin.generation)
    assert idle.get_sender_id() == "humanization"
    assert idle.role == "member"
    assert idle.unified_msg_origin == str(idle.route)
    await consume(plugin.observe(Event(message_id="2")))
    plugin.adapter.request = AsyncMock()
    assert await consume(plugin.observe(idle)) == []
    plugin.adapter.request.assert_not_called()
    assert (await plugin.storage.session(message.scope))["human_count"] == 2


async def test_missing_native_completion_is_not_retried_or_recorded(plugin):
    event = Event(direct=True)
    await consume(plugin.observe(event))
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="hi"))
    turn = plugin.participate(event)
    await anext(turn)
    response = LLMResponse(role="assistant", completion_text="你好")
    await plugin.validate(event, response)
    result = await anext(turn)
    assert result.get_plain_text() == "你好"
    # A different decorator can clear the result without reaching RespondStage.
    event.clear_result()
    assert await consume(turn) == []
    assert not event.sent
    assert not await plugin.storage.rows("SELECT * FROM messages WHERE direction='out'")
    assert (await plugin.storage.rows("SELECT * FROM reply_runs"))[0][
        "status"
    ] == "unconfirmed"


async def test_closed_turn_releases_all_cached_output(plugin):
    event = Event(direct=True)
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    await consume(plugin.observe(event))
    generator = plugin.participate(event)
    await anext(generator)
    await plugin.validate(
        event, LLMResponse(role="assistant", completion_text="你好$你看")
    )
    state = event.get_extra("humanization_turn")
    assert len(state["outputs"]) == 2
    await generator.aclose()
    assert state == {} and event.get_extra("humanization_turn") is None
    assert not plugin.controller.lock(
        event.get_extra("humanization_message").scope
    ).locked()
    assert (await plugin.storage.rows("SELECT * FROM reply_runs"))[0][
        "status"
    ] == "unknown"
