"""Native pipeline and media contracts, without live models or transports."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from humanization_test.core.astrbot_adapter import IdleEvent
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.api.message_components import File, Image, Plain, Video
from astrbot.core.message.message_event_result import ResultContentType
from astrbot.core.pipeline.context_utils import call_handler
from astrbot.core.pipeline.process_stage.stage import ProcessStage
from astrbot.core.provider.entities import LLMResponse, ProviderRequest
from astrbot.core.star.session_llm_manager import SessionServiceManager


async def test_media_rows_contain_only_resource_tags(plugin):
    event = Event()
    event.message_obj.message = [
        Plain("看一下"),
        Image(file="https://example.com/private.png"),
        Video(file="https://example.com/private.mp4"),
        File(file="https://example.com/private.pdf", name="private.pdf"),
    ]
    await consume(plugin.observe(event))
    row = (await plugin.storage.rows("SELECT * FROM messages"))[0]
    assert row["text"] == "看一下[image][video][file]"
    assert "private" not in row["segments"]
    assert "https" not in row["segments"]


@pytest.mark.parametrize("direct, expected", [(True, 1), (False, 0)])
async def test_host_process_does_not_duplicate_or_override_gate(
    plugin, direct, expected
):
    event = Event(direct=direct)
    event.is_at_or_wake_command = True
    event.set_extra("activated_handlers", [SimpleNamespace(event_filters=[])])
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    await consume(plugin.observe(event))
    calls = []

    async def native_agent(event):
        calls.append(event.get_extra("provider_request"))
        response = LLMResponse(role="assistant", completion_text="你好$嗯")
        await plugin.validate(event, response)
        event.set_result(
            event.plain_result(response.completion_text).set_result_content_type(
                ResultContentType.LLM_RESULT
            )
        )
        yield

    async def handler(event):
        async for result in call_handler(event, plugin.participate):
            yield result

    stage = ProcessStage()
    stage.ctx = SimpleNamespace(astrbot_config={"provider_settings": {"enable": True}})
    stage.star_request_sub_stage = SimpleNamespace(process=handler)
    stage.agent_sub_stage = SimpleNamespace(process=native_agent)
    async for _ in stage.process(event):
        await plugin.defer_result(event)
        if event.get_result():
            await event.send(event.get_result())
            await plugin.after_sent(event)
            event.clear_result()
    assert len(calls) == expected
    assert len(event.sent) == expected * 2


async def test_idle_preserves_group_route_and_respects_disabled_group(
    plugin, monkeypatch
):
    source = Event()
    await consume(plugin.observe(source))
    state = await plugin.storage.session(source.get_extra("humanization_message").scope)
    idle = IdleEvent(plugin.context, source.platform_meta, state, plugin.generation)
    idle.session_id = "humanization_123"
    assert idle.unified_msg_origin == "onebot:GroupMessage:123"
    check = AsyncMock(return_value=False)
    monkeypatch.setattr(SessionServiceManager, "is_session_enabled", check)
    assert not await plugin.adapter.can_reply(idle)
    check.assert_awaited_once_with("onebot:GroupMessage:123")


async def test_filtered_command_cancels_remaining_idle_bubbles(plugin):
    source = Event()
    await consume(plugin.observe(source))
    message = source.get_extra("humanization_message")
    state = await plugin.storage.session(message.scope)
    idle = IdleEvent(plugin.context, source.platform_meta, state, plugin.generation)
    plugin.settings.proactive["enabled"] = True
    plugin.settings.proactive["quiet_enabled"] = False
    await plugin.storage.update_session(message.scope, last_human=0)
    state = await plugin.storage.session(message.scope)
    idle = IdleEvent(plugin.context, source.platform_meta, state, plugin.generation)
    plugin.controller.decide = AsyncMock(
        return_value=SimpleNamespace(reply=True, intent="开话题")
    )
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    generator = plugin.observe(idle)
    await anext(generator)
    await plugin.validate(
        idle, LLMResponse(role="assistant", completion_text="第一条$第二条")
    )
    result = await anext(generator)
    idle.set_result(result)
    await consume(plugin.observe(Event("/status", message_id="2")))
    await plugin.after_sent(idle)
    idle.clear_result()
    assert await consume(generator) == []
    state = await plugin.storage.session(message.scope)
    assert not state["idle_waiting"]
    assert state["human_count"] == 1
    assert (await plugin.storage.rows("SELECT * FROM reply_runs"))[0][
        "status"
    ] == "superseded"


async def test_invalid_output_repaired_once(plugin):
    event = Event(direct=True)
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    plugin.adapter.generate = AsyncMock(return_value="还是\n不合规")
    await consume(plugin.observe(event))
    turn = plugin.participate(event)
    await anext(turn)
    await plugin.validate(
        event, LLMResponse(role="assistant", completion_text="第一行\n第二行")
    )
    assert not event.is_stopped()
    assert await consume(turn) == []
    plugin.adapter.generate.assert_awaited_once()
    assert not event.sent


async def test_native_collector_binds_conversation_and_images(plugin, monkeypatch):
    conversation = SimpleNamespace(cid="test", history="[]")
    manager = SimpleNamespace(
        get_curr_conversation_id=AsyncMock(return_value=None),
        new_conversation=AsyncMock(return_value="test"),
        get_conversation=AsyncMock(return_value=conversation),
    )
    plugin.context.conversation_manager = manager
    event = Event()
    event.message_obj.message.append(Image(file="ignored"))
    monkeypatch.setattr(
        Image, "convert_to_file_path", AsyncMock(return_value="image.png")
    )
    request = await plugin.adapter.request(event)
    assert request.conversation is conversation
    assert request.image_urls == ["image.png"]
    assert request.prompt == "你好"
    manager.new_conversation.assert_awaited_once_with(
        event.unified_msg_origin, "onebot"
    )


async def test_cleared_replay_result_is_not_resurrected(plugin):
    event = Event(direct=True)
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    await consume(plugin.observe(event))
    turn = plugin.participate(event)
    await anext(turn)
    await plugin.validate(event, LLMResponse(role="assistant", completion_text="你好"))
    await anext(turn)
    event.clear_result()
    await plugin.defer_result(event)
    assert await consume(turn) == []
    assert not event.sent


async def test_entrypoint_loads_schema_and_populates_group_choices(
    tmp_path, monkeypatch
):
    from humanization_test.main import Humanization

    from astrbot.api import AstrBotConfig
    from astrbot.api.star import StarTools

    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "_conf_schema.json").read_text(encoding="utf-8"))
    config = AstrBotConfig(str(tmp_path / "config.json"), schema=schema)
    database = SimpleNamespace(
        get_umo_aliases=AsyncMock(
            return_value=[
                SimpleNamespace(
                    umo="onebot:GroupMessage:42_123",
                    creator_sender_id="42",
                    user_alias="",
                    auto_name="测试群",
                )
            ]
        )
    )
    context = SimpleNamespace(
        persona_manager=SimpleNamespace(get_persona=AsyncMock()),
        get_db=lambda: database,
    )
    monkeypatch.setattr(StarTools, "get_data_dir", lambda: tmp_path)
    instance = Humanization(context, config)
    await instance.initialize()
    try:
        options = config.schema["scope"]["items"]["sessions"]["options"]
        assert "onebot:GroupMessage:123" in options
        assert not instance.runtime.settings.scope["sessions"]
        assert instance.runtime.storage.path.exists()
    finally:
        await instance.terminate()
    assert all(task.done() for task in instance.runtime.tasks)
