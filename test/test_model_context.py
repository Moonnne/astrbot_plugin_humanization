"""Unified command filtering and cache-friendly auxiliary inputs."""

import asyncio
import copy
import json
from dataclasses import replace
from os.path import commonprefix
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from controller_helpers import plan_json
from diary_helpers import model_change, topic_change
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.api.message_components import Plain, Reply
from astrbot.core.agent.context.compressor import LLMSummaryCompressor
from astrbot.core.agent.hooks import BaseAgentRunHooks
from astrbot.core.agent.message import Message, TextPart
from astrbot.core.agent.response import AgentStats
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.runners.tool_loop_agent_runner import ToolLoopAgentRunner
from astrbot.core.astr_agent_hooks import MAIN_AGENT_HOOKS
from astrbot.core.pipeline.process_stage.follow_up import _ACTIVE_AGENT_RUNNERS
from astrbot.core.pipeline.process_stage.method.agent_sub_stages.internal import (
    InternalAgentSubStage,
)
from astrbot.core.provider.entities import LLMResponse, ProviderRequest, TokenUsage
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType, star_handlers_registry


@pytest.mark.parametrize(
    "enabled, compression",
    [(False, "none"), (True, "none"), (True, "truncate"), (True, "summary")],
)
async def test_native_writer_preserves_commands_excluded_from_inference(
    plugin, monkeypatch, enabled, compression
):
    plugin.settings.recorder["filter_commands"] = enabled
    history = [
        {"role": "user", "content": "old ordinary discussion " * 250},
        {"role": "assistant", "content": "old ordinary response"},
        {"role": "user", "content": "/status secret command"},
        {"role": "assistant", "content": "secret command result"},
        {"role": "user", "content": "recent ordinary discussion"},
        {"role": "assistant", "content": "recent ordinary response"},
    ]
    conversation = SimpleNamespace(
        cid="native", history=json.dumps(history), token_usage=0
    )
    request = ProviderRequest(
        prompt="current ordinary discussion",
        system_prompt="system",
        contexts=copy.deepcopy(history),
        conversation=conversation,
    )
    event = Event(direct=True)
    event.set_extra("humanization_turn", {"phase": "agent", "run": 1})

    async def begin(event, run_context):
        plugin.adapter.filter_agent_history(event, run_context)

    async def done(event, run_context, response):
        plugin.adapter.record_main_usage(event)
        plugin.adapter.restore_agent_history(event, run_context)

    callbacks = {
        EventType.OnAgentBeginEvent: begin,
        EventType.OnAgentDoneEvent: done,
    }
    monkeypatch.setitem(
        star_map, "humanization.context.test", SimpleNamespace(name="Humanization")
    )
    monkeypatch.setattr(
        star_handlers_registry,
        "get_handlers_by_event_type",
        lambda kind, **kw: (
            [
                SimpleNamespace(
                    handler_module_path="humanization.context.test",
                    handler_name=kind.name,
                    handler=callbacks[kind],
                )
            ]
            if kind in callbacks
            else []
        ),
    )
    seen = []

    async def reply(**payload):
        seen.extend(message.model_dump() for message in payload["contexts"])
        return LLMResponse(
            role="assistant",
            completion_text="native reply",
            usage=TokenUsage(input_other=100, input_cached=100, output=10),
        )

    provider = SimpleNamespace(
        provider_config={
            "id": "main",
            "max_context_tokens": 1000 if compression == "summary" else 0,
        },
        text_chat=reply,
    )
    compressor_provider = SimpleNamespace(
        provider_config={},
        text_chat=AsyncMock(
            return_value=LLMResponse(
                role="assistant", completion_text="ordinary discussion summary"
            )
        ),
    )
    runner = ToolLoopAgentRunner()
    await runner.reset(
        provider=provider,
        request=request,
        run_context=ContextWrapper(context=SimpleNamespace(event=event)),
        tool_executor=SimpleNamespace(),
        agent_hooks=MAIN_AGENT_HOOKS,
        enforce_max_turns=1 if compression == "truncate" else -1,
        custom_compressor=LLMSummaryCompressor(compressor_provider, keep_recent_ratio=0)
        if compression == "summary"
        else None,
    )
    monkeypatch.setitem(_ACTIVE_AGENT_RUNNERS, event.unified_msg_origin, runner)
    await consume(runner.step())
    assert runner.done()
    assert ("secret command" in str(seen)) is not enabled
    if compression == "summary":
        assert "secret command" not in str(compressor_provider.text_chat.call_args)
    writer = InternalAgentSubStage()
    writer.conv_manager = SimpleNamespace(update_conversation=AsyncMock())
    await writer._save_to_history(
        event,
        request,
        runner.get_final_llm_resp(),
        runner.run_context.messages,
        runner.stats,
    )
    saved = writer.conv_manager.update_conversation.call_args.kwargs["history"]
    assert [item for item in saved if "secret command" in str(item)] == history[2:4]
    assert "native reply" in str(saved)
    assert request.contexts == history
    if compression in ("truncate", "summary"):
        assert "old ordinary discussion" not in str(saved)
    assert "command_history" not in event.get_extra("humanization_turn")
    await plugin.log.flush()
    records = [
        json.loads(line)
        for line in (plugin.log.directory / "runtime.log")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    counters = [row["data"] for row in records if row["event"] == "model.usage"]
    assert len(counters) == 1
    assert counters[0]["purpose"] == "main"
    assert counters[0]["usage"]["input"] == 200
    assert counters[0]["cache_ratio"] == 0.5


async def test_default_filters_command_recording_and_quote(plugin):
    assert plugin.settings.recorder["filter_commands"] is True
    await consume(plugin.observe(Event("/status secret", message_id="command")))
    assert not await plugin.storage.rows("SELECT * FROM messages")
    event = Event()
    event.message_obj.message.append(
        Reply(id="command", chain=[Plain("/status secret")])
    )
    request = ProviderRequest(extra_user_content_parts=[])
    request.extra_user_content_parts.append(
        TextPart(text="<Quoted Message>\n/status secret")
    )
    plugin.adapter.filter_command_quote(event, request)
    assert request.extra_user_content_parts == []
    plugin.settings.recorder["filter_commands"] = False
    request.extra_user_content_parts.append(
        TextPart(text="<Quoted Message>\n/status secret")
    )
    plugin.adapter.filter_command_quote(event, request)
    assert len(request.extra_user_content_parts) == 1


async def test_gate_context_prefix_survives_changed_trigger_fields(plugin):
    plugin.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0, mode="scheduled"
    )
    event = Event()
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    generate = AsyncMock(return_value=plan_json(reply=False))
    plugin.controller.generate = generate
    await plugin.controller.decide(message, False, False)
    first = generate.call_args.args[2]
    await plugin.controller.decide(message, False, False, idle=True)
    second = generate.call_args.args[2]
    assert (
        first.split(',"recent_decisions":')[0]
        == second.split(',"recent_decisions":')[0]
    )
    payload = json.loads(first)
    assert isinstance(payload["context"], dict)
    assert payload["context"]["messages"][0]["message_id"] == message.message_id
    assert payload["recent_decisions"] == []
    assert len(json.loads(second)["recent_decisions"]) == 1
    assert payload["reply_required"] is False and "now" in payload


async def test_gate_topic_prefix_survives_window_rollover_without_stale_messages(
    plugin,
):
    plugin.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0, mode="scheduled"
    )
    plugin.storage.retention = 100
    base = plugin.adapter.snapshot(Event())
    for index in range(1, 31):
        await plugin.storage.append(replace(base, message_id=str(index)))
    await plugin.storage.commit_summary(
        base.scope, base.day, [topic_change("stable topic " * 80)], 1, 1, 1
    )
    generate = AsyncMock(return_value=plan_json(reply=False))
    plugin.controller.generate = generate
    await plugin.controller.decide(replace(base, message_id="30"), False, False)
    first = generate.call_args.args[2]
    latest = replace(base, message_id="31")
    await plugin.storage.append(latest)
    await plugin.controller.decide(latest, False, False)
    second = generate.call_args.args[2]
    await plugin.controller.decide(latest, False, False, idle=True)
    third = json.loads(generate.call_args.args[2])
    before, after = json.loads(first), json.loads(second)
    assert [row["message_id"] for row in before["context"]["messages"]] == [
        str(index) for index in range(1, 31)
    ]
    assert [row["message_id"] for row in after["context"]["messages"]] == [
        str(index) for index in range(2, 32)
    ]
    assert before["context"]["topics"] == after["context"]["topics"]
    assert before["context"]["topics"]["included_count"] == 1
    assert third["recent_decisions"][0] == after["recent_decisions"][0]
    assert first.split(',"messages":')[0] == second.split(',"messages":')[0]
    # Compare against the previous assembly order with the very same data.
    old_payloads = []
    for payload in (before, after):
        context = payload["context"]
        old_payloads.append(
            json.dumps(
                {
                    **payload,
                    "context": {
                        "notice": context["notice"],
                        "messages": context["messages"],
                        "topics": context["topics"],
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    assert len(commonprefix([first, second])) > len(commonprefix(old_payloads)) + 1000
    assert len(first) == len(old_payloads[0])
    assert len({call.args[1] for call in generate.call_args_list}) == 1
    other = json.loads(await plugin.prompts.context("other", for_controller=True))
    assert other["messages"] == [] and other["topics"]["items"] == []


@pytest.mark.parametrize("observed", ["same", "different", "missing"])
async def test_main_focus_only_deduplicates_exact_visible_message(plugin, observed):
    event = Event("unique focus content " * 100)
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    context = json.loads(await plugin.prompts.context(message.scope))
    focus = {"message": copy.deepcopy(context["messages"][0]), "topic": None}
    original_focus = copy.deepcopy(focus)
    if observed == "different":
        context["messages"][0]["text"] = "same ID but different content"
    elif observed == "missing":
        context["messages"] = []
    observation = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    planning = json.loads(plan_json())
    original_plan = copy.deepcopy(planning)
    history = [{"role": "user", "content": "native history"}]
    request = ProviderRequest(prompt="native input", contexts=copy.deepcopy(history))
    plugin.adapter.inject_observation(request, observation, "", planning, focus)
    injected = request.extra_user_content_parts[-1].text
    sent_focus = json.loads(injected.split("：", 1)[1])["focus"]
    if observed == "same":
        assert sent_focus["message"] == {"message_id": message.message_id}
        assert "unique focus content" not in injected
        assert "unique focus content" in request.extra_user_content_parts[0].text
        assert len(injected) < len(json.dumps(original_focus, ensure_ascii=False))
    else:
        assert sent_focus == original_focus
    assert focus == original_focus and planning == original_plan
    assert request.contexts == history and request.prompt == "native input"
    assert all(
        part.model_dump_for_context()["_no_save"]
        for part in request.extra_user_content_parts
    )


async def test_auxiliary_debug_log_records_estimate_and_provider_usage(plugin):
    plugin.log.debug_mode = True
    plugin.context.llm_generate = AsyncMock(
        return_value=LLMResponse(
            role="assistant",
            completion_text="reply",
            usage=TokenUsage(input_other=25, input_cached=75, output=5),
        )
    )
    assert (
        await plugin.adapter.generate("gate", "stable rules", "changing input")
        == "reply"
    )
    await plugin.log.flush()
    rows = [
        json.loads(line)
        for line in (plugin.log.directory / "dev.log")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert rows[-2]["data"]["estimated_input"] > 0
    assert rows[-1]["data"]["usage"] == {
        "input": 100,
        "input_cached": 75,
        "output": 5,
        "total": 105,
    }


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("purpose", ["controller", "recorder", "format_repair"])
async def test_auxiliary_call_counters_are_file_only_in_both_modes(
    plugin, debug, purpose
):
    plugin.log.debug_mode = debug
    plugin.log.console = Mock()
    plugin.context.llm_generate = AsyncMock(
        return_value=LLMResponse(
            role="assistant",
            completion_text="private answer",
            usage=TokenUsage(input_other=100, output=5),
            raw_completion={
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 5,
                    "prompt_cache_hit_tokens": 80,
                    "prompt_cache_miss_tokens": 20,
                }
            },
        )
    )
    await plugin.adapter.generate(
        "provider", "private rules", "private input", purpose=purpose
    )
    await plugin.log.flush()
    rows = [
        json.loads(line)
        for line in (plugin.log.directory / "runtime.log")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    records = [row["data"] for row in rows if row["event"] == "model.usage"]
    assert len(records) == 1
    record = records[0]
    assert record["purpose"] == purpose
    assert record["estimated_input"] > 0
    assert record["usage"] == {
        "input": 100,
        "input_cached": 80,
        "output": 5,
        "total": 105,
    }
    assert record["cache_ratio"] == 0.8 and record["cache_source"] == "provider"
    assert record["provider_details"]["cache_miss"] == 20
    assert "private" not in str(record)
    assert plugin.log.console.mock_calls == []


@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError])
async def test_failed_auxiliary_call_records_status_without_fake_usage(plugin, error):
    plugin.log.console = Mock()
    plugin.context.llm_generate = AsyncMock(side_effect=error("private failure"))
    with pytest.raises(error):
        await plugin.adapter.generate("provider", "rules", "input", purpose="recorder")
    await plugin.log.flush()
    rows = [
        json.loads(line)
        for line in (plugin.log.directory / "runtime.log")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    record = [row["data"] for row in rows if row["event"] == "model.usage"][0]
    assert record["usage"] is None and record["cache_ratio"] is None
    assert record["status"] == (
        "cancelled" if error.__name__ == "CancelledError" else "error"
    )
    assert "private failure" not in str(record)
    assert plugin.log.console.mock_calls == []


async def test_native_step_counters_are_logged_once_and_not_cumulatively_twice(plugin):
    event = Event()
    response = LLMResponse(
        role="assistant",
        completion_text="private reply",
        usage=TokenUsage(input_other=50, input_cached=150, output=10),
    )
    stats = AgentStats(
        token_usage=TokenUsage(input_other=25, input_cached=75, output=5),
        current_context_tokens=100,
        end_time=1,
    )
    runner = SimpleNamespace(
        stats=stats,
        provider=SimpleNamespace(provider_config={"id": "main"}),
        run_context=SimpleNamespace(
            messages=[
                Message(role="user", content="private input"),
                Message(role="assistant", content="tool call"),
            ]
        ),
        get_final_llm_resp=Mock(return_value=None),
        was_aborted=Mock(return_value=False),
    )
    event.set_extra(
        "humanization_turn",
        {"run": 1, "usage_runner": runner, "usage_previous": TokenUsage()},
    )
    plugin.adapter.record_main_usage(event)
    plugin.adapter.record_main_usage(event)
    stats.token_usage = stats.token_usage + response.usage
    stats.current_context_tokens = 200
    stats.end_time = 2
    runner.get_final_llm_resp.return_value = response
    plugin.adapter.record_main_usage(event)
    plugin.adapter.record_main_usage(event)
    await plugin.log.flush()
    rows = [
        json.loads(line)
        for line in (plugin.log.directory / "runtime.log")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    records = [row["data"] for row in rows if row["event"] == "model.usage"]
    assert [record["usage"]["input"] for record in records] == [100, 200]
    assert [record["usage"]["output"] for record in records] == [5, 10]
    assert all(record["scope"] == "native_step" for record in records)


async def test_summary_diary_changes_do_not_change_message_prefix(plugin):
    event = Event()
    await consume(plugin.observe(event))
    scope = event.get_extra("humanization_message").scope
    generate = AsyncMock(return_value=model_change("updated diary"))
    plugin.summarizer.generate = generate
    pending = await plugin.storage.recent(scope, 100)
    session = await plugin.storage.session(scope)
    await plugin.summarizer.summarize(session, pending)
    first = generate.call_args.args[2]
    await plugin.summarizer.summarize(session, pending)
    second = generate.call_args.args[2]
    assert (
        first.split(',"existing_diaries":')[0]
        == second.split(',"existing_diaries":')[0]
    )
    assert (
        json.loads(first)["existing_diaries"] != json.loads(second)["existing_diaries"]
    )
    assert list(json.loads(first)) == [
        "date",
        "messages",
        "already_summarized_through_seq",
        "existing_diaries",
        "coverage_gap",
        "output_char_limit",
        "instruction",
    ]


async def test_shared_model_observations_render_topics_once_and_report_omissions(
    plugin,
):
    event = Event()
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    await plugin.storage.commit_summary(
        message.scope,
        message.day,
        [topic_change("old topic"), topic_change("new topic", 2)],
        1,
        1,
        1,
    )
    latest = (await plugin.storage.diaries(message.scope))[0]["topics"][-1]
    plugin.settings.recorder["diary_context_chars"] = len(
        json.dumps(latest, ensure_ascii=False, separators=(",", ":"))
    )
    context = json.loads(await plugin.prompts.context(message.scope))
    diary = context["diaries"][0]
    assert "topics" not in diary
    assert diary["omitted_topics"] == 1
    assert "[Topic]new topic" in diary["body"]
    assert "[Topic]old topic" not in diary["body"]
    assert len((await plugin.storage.diaries(message.scope))[0]["topics"]) == 2


async def test_unified_filter_excludes_existing_command_observations(plugin):
    plugin.settings.recorder["filter_commands"] = False
    event = Event("/status secret command")
    await consume(plugin.observe(event))
    scope = plugin.adapter.snapshot(event).scope
    assert "secret command" in await plugin.prompts.context(scope)
    plugin.settings.recorder["filter_commands"] = True
    assert "secret command" not in await plugin.prompts.context(scope)
    assert "secret command" in (await plugin.storage.recent(scope, 1))[0]["text"]


async def test_summary_overlap_reuses_previous_message_prefix(plugin):
    first_event = Event("first discussion", message_id="first")
    await consume(plugin.observe(first_event))
    scope = first_event.get_extra("humanization_message").scope
    generate = AsyncMock(
        side_effect=[model_change("updated diary", 1), model_change("new diary", 2)]
    )
    plugin.summarizer.generate = generate
    await plugin.summarizer.summarize(
        await plugin.storage.session(scope), await plugin.storage.recent(scope, 100)
    )
    first = json.loads(generate.call_args.args[2])
    await consume(plugin.observe(Event("new discussion", message_id="second")))
    pending = await plugin.storage.rows(
        "SELECT * FROM messages WHERE scope=? AND seq>1 ORDER BY seq", (scope,)
    )
    await plugin.summarizer.summarize(await plugin.storage.session(scope), pending)
    second = json.loads(generate.call_args.args[2])
    assert second["messages"][: len(first["messages"])] == first["messages"]
    assert first["already_summarized_through_seq"] == 0
    assert second["already_summarized_through_seq"] == 1
    assert [row["seq"] for row in second["messages"]] == [1, 2]


async def test_abort_restores_commands_before_native_save(plugin):
    assert plugin.settings.recorder["filter_commands"] is True
    event = Event()
    event.set_extra("humanization_turn", {"phase": "agent"})
    original = [
        Message(role="user", content="/status secret"),
        Message(role="assistant", content="command reply"),
        Message(role="user", content="ordinary input"),
    ]
    context = ContextWrapper(context=SimpleNamespace(event=event), messages=original)

    class Hooks(BaseAgentRunHooks):
        async def on_agent_done(self, run_context, response):
            plugin.adapter.restore_agent_history(event, run_context)

    request = ProviderRequest(prompt="ordinary input")
    runner = ToolLoopAgentRunner()
    await runner.reset(
        provider=SimpleNamespace(provider_config={}),
        request=request,
        run_context=context,
        tool_executor=SimpleNamespace(),
        agent_hooks=Hooks(),
    )
    context.messages = original
    plugin.adapter.filter_agent_history(event, context)
    await runner._finalize_aborted_step()
    assert context.messages[:3] == original
    assert "command_history" not in event.get_extra("humanization_turn")
