"""Native pipeline and media contracts, without live models or transports."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from humanization_test.core.astrbot_adapter import IdleEvent
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.api.message_components import File, Image, Plain, Reply, Video
from astrbot.core.agent.message import TextPart, bind_checkpoint_messages
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


async def test_custom_command_prefix_never_enters_recording_or_gate(plugin):
    plugin.settings.recorder["command_prefixes"] = ["/", "!"]
    event = Event("!task private command")
    plugin.controller.generate = AsyncMock()
    await consume(plugin.observe(event))
    assert await consume(plugin.participate(event)) == []
    assert event.call_llm
    assert not await plugin.storage.rows("SELECT * FROM messages")
    context = json.loads(
        await plugin.prompts.context(plugin.adapter.snapshot(event).scope)
    )
    assert context["messages"] == []
    plugin.controller.generate.assert_not_awaited()


@pytest.mark.parametrize("only_commands", [False, True])
async def test_existing_command_records_are_not_read_by_context_or_summary(
    plugin, only_commands
):
    plugin.settings.recorder["filter_commands"] = False
    await consume(
        plugin.observe(Event("/old private command", message_id="old-command"))
    )
    if not only_commands:
        await consume(plugin.observe(Event("normal conversation", message_id="normal")))
    await consume(
        plugin.observe(Event("/tail private command", message_id="tail-command"))
    )
    plugin.settings.recorder.update(
        filter_commands=True, summary_provider="summary", summary_every=1
    )
    scope = plugin.adapter.snapshot(Event()).scope
    context = await plugin.prompts.context(scope)
    assert "private command" not in context
    generate = AsyncMock(return_value='{"changes":[]}')
    plugin.summarizer.generate = generate
    await plugin.summarizer.tick()
    state = await plugin.storage.session(scope)
    assert state["cursor"] == state["last_seq"]
    assert state["summarized_count"] == state["human_count"]
    if only_commands:
        generate.assert_not_awaited()
        assert not await plugin.storage.diaries(scope)
    else:
        assert "private command" not in generate.call_args.args[2]


async def test_native_command_history_and_quote_are_filtered_without_changing_storage(
    plugin,
):
    plugin.settings.recorder["command_prefixes"] = ["/", "!"]
    assert plugin.settings.recorder["filter_commands"] is True
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "normal reply"},
        {"role": "user", "content": "/status private input"},
        {"role": "system", "content": "private command attachment"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "command-tool"}]},
        {
            "role": "tool",
            "content": "private tool result",
            "tool_call_id": "command-tool",
        },
        {"role": "user", "content": [{"type": "text", "text": "!task private input"}]},
        {"role": "assistant", "content": "private command reply"},
        {"role": "user", "content": "normal latest"},
    ]
    stored = json.dumps(history)
    event = Event("regular conversation")
    event.message_obj.message.append(
        Reply(id="command", chain=[Plain("/status secret")])
    )
    request = ProviderRequest(contexts=json.loads(stored))
    request.extra_user_content_parts = [
        TextPart(text="<Quoted Message>\n/status secret"),
        TextPart(text="other context"),
    ]
    plugin.adapter.filter_command_quote(event, request)
    assert request.contexts == history
    assert [part.text for part in request.extra_user_content_parts] == ["other context"]
    event.set_extra("humanization_turn", {"phase": "agent"})
    run_context = SimpleNamespace(messages=bind_checkpoint_messages(request.contexts))
    await plugin.adapter.filter_agent_history(event, run_context)
    assert [message.role for message in run_context.messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert "private" not in str(run_context.messages)
    plugin.adapter.restore_agent_history(event, run_context)
    assert [message.model_dump(exclude_none=True) for message in run_context.messages][
        0
    ]["content"] == "hello"
    assert len(run_context.messages) == len(history)
    assert "command_history" not in event.get_extra("humanization_turn")
    assert stored == json.dumps(history)
    plugin.settings.recorder["filter_commands"] = False
    request.contexts = json.loads(stored)
    plugin.adapter.filter_command_quote(event, request)
    assert request.contexts == history


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
        return_value=SimpleNamespace(
            reply=True,
            intent="开话题",
            reason="reply",
            planning=None,
            focus=None,
            record_id=None,
        )
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
    assert config["controller"]["mode"] == "scheduled"
    assert config["controller"]["force_at"] is True
    assert next(reversed(schema)) == "logging"
    assert "danger" not in schema
    assert list(schema["recorder"]["items"])[:2] == ["enabled", "summary_provider"]
    assert config["recorder"]["filter_commands"] is True
    assert "filter_llm_commands" not in schema["recorder"]["items"]
    assert list(schema["controller"]["items"])[:2] == ["enabled", "gate_provider"]
    for name in ("wait_min_seconds", "wait_max_seconds"):
        assert schema["controller"]["items"][name]["condition"] == {"mode": "scheduled"}
    for name in ("sessions", "manual_sessions"):
        assert schema["scope"]["items"][name]["condition"] == {"all_sessions": False}
    for name in ("blacklist_sessions", "blacklist_manual_sessions", "blacklist_action"):
        assert schema["scope"]["items"][name]["condition"] == {"all_sessions": True}
    assert (
        config["scope"]["outside_action"]
        == config["scope"]["blacklist_action"]
        == "ignore"
    )
    config["prompts"]["behavior"] = ""
    config["prompts"]["group"] = "  "
    config["prompts"]["expression"] = "Existing custom expression"
    config["logging"]["runtime_max_mb"] = 3
    config.save_config()
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
        register_web_api=Mock(),
        registered_web_apis=[],
    )
    monkeypatch.setattr(StarTools, "get_data_dir", lambda: tmp_path)
    instance = Humanization(context, config)
    await instance.initialize()
    try:
        options = config.schema["scope"]["items"]["sessions"]["options"]
        assert "onebot:GroupMessage:123" in options
        assert (
            config.schema["scope"]["items"]["blacklist_sessions"]["options"] == options
        )
        assert not instance.runtime.settings.scope["sessions"]
        assert instance.runtime.storage.path.exists()
        saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8-sig"))
        for name in ("behavior", "group"):
            assert not saved["prompts"][name].strip()
            assert (
                await instance.runtime.prompts.fragment(name)
                == instance.runtime.prompts.text[name].strip()
            )
        assert saved["prompts"]["expression"] == "Existing custom expression"
        assert set(instance.runtime.prompts.text) == {
            "gate",
            "summary",
            "output",
            "behavior",
            "expression",
            "group",
            "private",
        }
        assert instance.runtime.log.limits["runtime.log"] == 3 * 1024**2
    finally:
        await instance.terminate()
    assert all(task.done() for task in instance.runtime.tasks)


@pytest.mark.parametrize("force_at", [True, False])
async def test_force_option_and_default_mode_survive_configuration_reload(
    tmp_path, monkeypatch, config, force_at
):
    from humanization_test.main import Humanization

    from astrbot.api import AstrBotConfig
    from astrbot.api.star import StarTools

    path = tmp_path / "config.json"
    config["controller"]["at_weight"] = 0.5
    config["controller"]["force_at"] = force_at
    config["controller"]["names"] = ["睦"]
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(StarTools, "get_data_dir", lambda: tmp_path)
    context = SimpleNamespace(persona_manager=SimpleNamespace(get_persona=AsyncMock()))
    for _ in range(2):
        schema = json.loads(
            (Path(__file__).resolve().parents[1] / "_conf_schema.json").read_text(
                encoding="utf-8"
            )
        )
        loaded = AstrBotConfig(str(path), schema=schema)
        instance = Humanization(context, loaded)
        await instance.runtime.initialize()
        try:
            assert loaded["controller"]["mode"] == "scheduled"
            assert loaded["controller"]["robot_name"] == "Bot"
            assert loaded["controller"]["names"] == ["睦"]
            assert loaded["controller"]["force_at"] is force_at
            assert loaded.schema["controller"]["items"]["force_at"]["default"] is True
        finally:
            await instance.terminate()
    assert (
        json.loads(path.read_text(encoding="utf-8-sig"))["controller"]["force_at"]
        is force_at
    )
