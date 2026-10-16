"""Structured plans, bounded persistent state and native reply execution."""

import json
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from controller_helpers import plan_data, plan_json
from diary_helpers import topic_change
from humanization_test.core.controller.protocol import ControllerProtocol
from humanization_test.core.settings import Settings
from test_host_contract import Event, consume, replay
from test_host_contract import plugin as plugin

from astrbot.core.provider.entities import LLMResponse, ProviderRequest

CONTEXT = {"messages": [{"message_id": "1"}], "topics": {"items": [{"id": 23}]}}


@pytest.mark.parametrize(
    "path,value",
    [
        ("reply", "true"),
        ("reply", 1),
        ("reason", ""),
        ("reason", "x" * 81),
        ("emotion.primary", "BAD"),
        ("emotion.intensity", True),
        ("emotion.intensity", 2),
        ("plan.intent", "BAD"),
        ("plan.style", ["WARM", "WARM"]),
        ("plan.style", ["WARM", "PLAYFUL", "CUTE"]),
        ("plan.style", [1]),
        ("plan.topic_id", True),
        ("plan.topic_id", 99),
        ("plan.target_message_id", "99"),
        ("plan.target_message_id", None),
        ("plan.guidance", "x" * 301),
        ("plan.participation", "BAD"),
        ("plan", None),
    ],
)
def test_plan_rejects_invalid_fields_and_invisible_focus(path, value):
    data = plan_data()
    target = data
    keys = path.split(".")
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    with pytest.raises(ValueError):
        ControllerProtocol.parse(json.dumps(data), CONTEXT, False)


@pytest.mark.parametrize(
    "raw",
    [
        "```json\n" + plan_json(reply=False) + "\n```",
        '{"action":"wait","intent":""}',
        json.dumps(plan_data() | {"time": "invented"}),
        " " * 4097,
    ],
)
def test_old_protocol_fences_extras_and_overlong_output_are_not_repaired(raw):
    with pytest.raises(ValueError):
        ControllerProtocol.parse(raw, CONTEXT, False)


def test_silent_anger_and_idle_start_are_valid_but_forced_silence_is_not():
    data = plan_data(reply=False, emotion="ANGER", intensity=2)
    assert ControllerProtocol.parse(json.dumps(data), CONTEXT, False) == data
    with pytest.raises(ValueError):
        ControllerProtocol.parse(json.dumps(data), CONTEXT, True)
    data = plan_data()
    data["plan"].update(participation="start", target_message_id=None)
    assert ControllerProtocol.parse(json.dumps(data), CONTEXT, False) == data
    data["reply"] = False
    with pytest.raises(ValueError):
        ControllerProtocol.parse(json.dumps(data), CONTEXT, False)


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("failure", ["timeout", "invalid", "silent"])
async def test_required_reply_survives_planner_failure_without_inventing_emotion(
    plugin, required, failure
):
    plugin.settings.controller.update(gate_provider="gate", group=1, cooldown_seconds=0)
    event = Event(direct=required)
    await consume(plugin.observe(event))
    response = plan_json(reply=False) if failure == "silent" else "invalid"
    plugin.controller.generate = AsyncMock(return_value=response)
    if failure == "timeout":
        plugin.controller.generate.side_effect = TimeoutError
    decision = await plugin.controller.decide(
        event.get_extra("humanization_message"), required, False
    )
    assert decision.reply is required
    rows = await plugin.storage.decisions(event.get_extra("humanization_message").scope)
    if not required and failure == "silent":
        assert decision.reason == "semantic_wait" and rows[0]["outcome"] == "observed"
    else:
        assert decision.planning is None and decision.record_id is None and rows == []


@pytest.mark.parametrize("finish", ["sent", "failed", "cancelled"])
async def test_forced_plan_is_temporary_and_records_actual_execution(plugin, finish):
    plugin.settings.controller.update(
        gate_provider="gate", group=0, cooldown_seconds=10000
    )
    event = Event(direct=True)
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    plugin.controller.generate = AsyncMock(
        return_value=plan_json(emotion="JOY", intensity=1)
    )
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="hi"))
    turn = plugin.participate(event)
    request = await anext(turn)
    plugin.controller.generate.assert_awaited_once()
    payload = json.loads(plugin.controller.generate.call_args.args[2])
    assert payload["reply_required"] is True and payload["now"].endswith("+08:00")
    rows = await plugin.storage.decisions(message.scope)
    assert rows[0]["outcome"] == "pending"
    await plugin.inject(event, request)
    part = request.extra_user_content_parts[-1].model_dump_for_context()
    assert part["_no_save"] is True and '"primary":"JOY"' in part["text"]
    assert '"message_id":"1"' in part["text"]
    if finish == "sent":
        await plugin.validate(
            event, LLMResponse(role="assistant", completion_text="好啊")
        )
        await replay(plugin, event, turn)
    elif finish == "failed":
        assert await consume(turn) == []
    else:
        await turn.aclose()
    rows = await plugin.storage.decisions(message.scope)
    assert (
        rows[0]["outcome"]
        == {"sent": "processed", "failed": "failed", "cancelled": "superseded"}[finish]
    )
    assert event.get_extra("humanization_turn") is None


async def test_history_is_bounded_per_scope_survives_restart_and_omits_old_guidance(
    plugin,
):
    plugin.settings.controller.update(gate_provider="gate", group=1, cooldown_seconds=0)
    event = Event()
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    for index in range(12):
        await plugin.storage.record_decision(
            message.scope,
            plan_data(guidance="private old guidance"),
            index,
            1,
            1,
            "message",
            False,
        )
    await plugin.storage.record_decision(
        "other", plan_data(reply=False), 1, 1, 1, "message", False
    )
    rows = await plugin.storage.decisions(message.scope)
    assert len(rows) == 10 and rows[0]["created_at"] == 2
    assert len(await plugin.storage.decisions("other")) == 1
    await plugin.storage.close()
    await plugin.storage.open()
    assert all(
        row["outcome"] == "unconfirmed"
        for row in await plugin.storage.decisions(message.scope)
    )
    plugin.controller.generate = AsyncMock(
        return_value=plan_json(reply=False, emotion="ANGER", intensity=1)
    )
    await plugin.controller.decide(message, False, False)
    payload = json.loads(plugin.controller.generate.call_args.args[2])
    assert len(payload["recent_decisions"]) == 10
    assert "private old guidance" not in plugin.controller.generate.call_args.args[2]
    assert all("age_seconds" not in row for row in payload["recent_decisions"])
    assert payload["recent_decisions"][0]["time"] == "1970-01-01T08:00:02+08:00"
    assert (await plugin.storage.decisions(message.scope))[-1]["outcome"] == "observed"


@pytest.mark.parametrize("mode", ["all", "today", "global"])
async def test_resets_clear_decisions_and_late_result_cannot_recreate_them(
    plugin, mode
):
    event = Event()
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    key = await plugin.storage.record_decision(
        message.scope, plan_data(), 1, 1, 1, "message", True
    )
    if mode == "global":
        await plugin.storage.reset_all()
    else:
        await plugin.storage.reset(
            message.scope, message.day if mode == "today" else None
        )
    await plugin.storage.finish_decision(key, "processed")
    assert await plugin.storage.decisions(message.scope) == []


async def test_controller_reads_thirty_messages_and_topics_across_more_than_two_days(
    plugin,
):
    plugin.storage.retention = 100
    base = plugin.adapter.snapshot(Event())
    for index in range(35):
        await plugin.storage.append(replace(base, message_id=str(index)))
        await plugin.storage.commit_summary(
            base.scope,
            f"2026-09-{index // 12 + 1:02}",
            [topic_change(f"topic {index}", index)],
            index,
            index,
            index,
        )
    context = json.loads(await plugin.prompts.context(base.scope, for_controller=True))
    assert len(context["messages"]) == 30
    topics = context["topics"]
    assert topics["candidate_count"] == topics["included_count"] == 30
    assert len({row["day"] for row in topics["items"]}) == 3
    plugin.settings.controller["topic_context_chars"] = 1
    context = json.loads(await plugin.prompts.context(base.scope, for_controller=True))
    assert context["topics"]["omitted_count"] == 30
    assert context["topics"]["items"] == []
    plugin.settings.controller["context_topics"] = 0
    assert (
        json.loads(await plugin.prompts.context(base.scope, for_controller=True))[
            "topics"
        ]["candidate_count"]
        == 0
    )
    assert len(await plugin.storage.rows("SELECT * FROM diary_topics")) == 35


async def test_focused_old_topic_is_carried_into_main_observation(plugin):
    plugin.settings.controller.update(gate_provider="gate", group=1, cooldown_seconds=0)
    event = Event()
    await consume(plugin.observe(event))
    message = event.get_extra("humanization_message")
    await plugin.storage.commit_summary(
        message.scope, "2020-01-01", [topic_change("old focus")], 1, 1, 1
    )
    topic = (await plugin.storage.rows("SELECT id FROM diary_topics"))[0]["id"]
    data = plan_data()
    data["plan"].update(participation="join", topic_id=topic, target_message_id=None)
    plugin.controller.generate = AsyncMock(return_value=json.dumps(data))
    decision = await plugin.controller.decide(message, False, False)
    assert decision.reply and decision.focus["topic"]["topic"] == "old focus"
    plugin.settings.recorder["diary_context_chars"] = 1
    request = ProviderRequest(prompt="hi")
    plugin.adapter.inject_observation(
        request,
        await plugin.prompts.context(message.scope),
        decision.intent,
        decision.planning,
        decision.focus,
    )
    assert "old focus" not in request.extra_user_content_parts[0].text
    assert "old focus" in request.extra_user_content_parts[1].text


@pytest.mark.parametrize(
    "key,value",
    [
        ("context_topics", -1),
        ("context_topics", True),
        ("topic_context_chars", 0),
        ("topic_context_chars", 1.5),
    ],
)
def test_controller_observation_config_validation(config, key, value):
    config["controller"][key] = value
    with pytest.raises(ValueError, match=key):
        Settings(config)
