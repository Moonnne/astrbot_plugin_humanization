"""Concise auxiliary-model outcomes without changing requests or decisions."""

import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from humanization_test.core.controller import controller as controller_module
from humanization_test.core.recorder import summarizer as summarizer_module
from test_host_contract import plugin as plugin
from test_logging import entries
from test_management import admin_event
from test_management import managed as managed


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("private", [False, True])
async def test_recorder_completion_reports_scope_actual_rows_and_duration(
    managed, monkeypatch, debug, private
):
    managed.log.debug_mode = debug
    managed.settings.scope["all_sessions"] = True
    managed.settings.recorder.update(summary_provider="summary", summary_every=2)
    for number in range(1, 4):
        event = admin_event(f"private source {number}", private=private)
        if not private:
            event.session.session_id = "42_123"
        event.message_obj.message_id = str(number)
        message = managed.adapter.snapshot(event)
        await managed.storage.append(message)
    await managed.storage.commit_summary(
        message.scope, message.day, "private older diary", 1, 1, time.time()
    )
    clock = SimpleNamespace(now=100)
    monkeypatch.setattr(summarizer_module, "perf_counter", lambda: clock.now)

    async def generate(*args, **kwargs):
        clock.now += 2.5
        return "private updated diary"

    managed.summarizer.generate = AsyncMock(side_effect=generate)
    await managed.summarizer.tick()
    await managed.log.flush()
    rows = entries(managed.log.directory / ("dev.log" if debug else "runtime.log"))
    complete = next(row for row in rows if row["event"] == "summary.complete")
    assert complete["data"] == {
        "conversation": "onebot:FriendMessage:42"
        if private
        else "onebot:GroupMessage:123",
        "message_count": 2,
        "context_count": 3,
        "duration_seconds": 2.5,
    }
    managed.summarizer.generate.assert_awaited_once()
    assert (await managed.storage.session(message.scope))["cursor"] == 3
    assert (await managed.storage.diaries(message.scope))[-1][
        "body"
    ] == "private updated diary"
    records = [
        call
        for call in managed.log.console.log.call_args_list
        if call.args[2] == "summary.complete"
    ]
    assert len(records) == int(not debug)
    if records:
        assert records[0].args[0] == logging.INFO
        assert json.loads(records[0].args[3]) == complete["data"]
    if not debug:
        raw = (managed.log.directory / "runtime.log").read_text(encoding="utf-8")
        assert "private source" not in raw and "private updated diary" not in raw
    else:
        assert not managed.log.console.mock_calls


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("failure", ["timeout", "empty_result"])
async def test_recorder_failure_reports_scope_duration_and_uncommitted_count(
    managed, monkeypatch, debug, failure
):
    managed.log.debug_mode = debug
    managed.settings.recorder.update(summary_provider="summary", summary_every=1)
    event = admin_event("private source")
    event.session.session_id = "42_123"
    message = managed.adapter.snapshot(event)
    await managed.storage.append(message)
    clock = SimpleNamespace(now=100)
    monkeypatch.setattr(summarizer_module, "perf_counter", lambda: clock.now)

    async def generate(*args, **kwargs):
        clock.now += 3.25
        if failure == "timeout":
            raise TimeoutError("private provider error")
        return "  "

    managed.summarizer.generate = AsyncMock(side_effect=generate)
    await managed.summarizer.tick()
    await managed.log.flush()
    rows = entries(managed.log.directory / ("dev.log" if debug else "runtime.log"))
    failed = next(row for row in rows if row["event"] == "summary.failed")
    assert failed["level"] == "ERROR"
    assert failed["data"]["conversation"] == "onebot:GroupMessage:123"
    assert failed["data"]["message_count"] == 0
    assert failed["data"]["candidate_count"] == 1
    assert failed["data"]["duration_seconds"] == 3.25
    assert failed["data"]["error_type"] == (
        "TimeoutError" if failure == "timeout" else "ValueError"
    )
    assert not any(row["event"] == "summary.complete" for row in rows)
    assert (await managed.storage.session(message.scope))["cursor"] == 0
    assert not await managed.storage.diaries(message.scope)
    records = [
        call
        for call in managed.log.console.log.call_args_list
        if call.args[2] == "summary.failed"
    ]
    assert len(records) == int(not debug)
    if records:
        assert records[0].args[0] == logging.ERROR
        assert "private provider error" not in str(records)
    else:
        assert not managed.log.console.mock_calls


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("action", ["reply", "wait"])
async def test_controller_logs_existing_plan_without_changing_protocol_or_intent(
    managed, monkeypatch, debug, action
):
    managed.log.debug_mode = debug
    managed.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0
    )
    event = admin_event("private source")
    event.session.session_id = "42_123"
    message = managed.adapter.snapshot(event)
    await managed.storage.append(message)
    clock = SimpleNamespace(now=100)
    monkeypatch.setattr(controller_module, "perf_counter", lambda: clock.now)
    intent = "用轻松口吻接话，带一点调侃。" + "x" * 150 + "private plan tail"

    async def generate(*args, **kwargs):
        clock.now += 1.125
        return json.dumps({"action": action, "intent": intent})

    managed.controller.generate = AsyncMock(side_effect=generate)
    decision = await managed.controller.decide(message, False, False)
    assert decision.reply is (action == "reply") and decision.intent == intent
    managed.controller.generate.assert_awaited_once()
    system = managed.controller.generate.call_args.args[1]
    assert system.startswith(managed.prompts.text["gate"])
    assert "emotion" not in system
    await managed.log.flush()
    rows = entries(managed.log.directory / ("dev.log" if debug else "runtime.log"))
    complete = next(row for row in rows if row["event"] == "gate.complete")
    assert complete["data"] == {
        "conversation": "onebot:GroupMessage:123",
        "action": action,
        "intent": intent[:120],
        "duration_seconds": 1.125,
    }
    records = [
        call
        for call in managed.log.console.log.call_args_list
        if call.args[2] == "gate.complete"
    ]
    assert len(records) == int(not debug)
    if records:
        assert records[0].args[0] == logging.INFO
        assert "private source" not in str(records)
        assert "private plan tail" not in str(records)
    else:
        assert not managed.log.console.mock_calls
        original = next(row for row in rows if row["event"] == "gate.decision")
        assert original["data"]["intent"] == intent


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("failure", ["timeout", "invalid_json"])
async def test_controller_error_keeps_wait_decision_and_reports_error_metadata(
    managed, monkeypatch, debug, failure
):
    managed.log.debug_mode = debug
    managed.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0
    )
    message = managed.adapter.snapshot(admin_event("private source", private=True))
    await managed.storage.append(message)
    clock = SimpleNamespace(now=100)
    monkeypatch.setattr(controller_module, "perf_counter", lambda: clock.now)

    async def generate(*args, **kwargs):
        clock.now += 4
        if failure == "timeout":
            raise TimeoutError("private provider error")
        return "private invalid response"

    managed.controller.generate = AsyncMock(side_effect=generate)
    # Private activity must pass its existing probability gate.
    managed.settings.controller["private"] = 1
    decision = await managed.controller.decide(message, False, False)
    assert not decision.reply and decision.reason == "error"
    await managed.log.flush()
    rows = entries(managed.log.directory / ("dev.log" if debug else "runtime.log"))
    failed = next(row for row in rows if row["event"] == "gate.failed")
    assert failed["data"]["conversation"] == "onebot:FriendMessage:42"
    assert failed["data"]["action"] == "wait"
    assert failed["data"]["duration_seconds"] == 4
    assert failed["data"]["error_type"] == (
        "TimeoutError" if failure == "timeout" else "JSONDecodeError"
    )
    assert not any(row["event"] == "gate.complete" for row in rows)
    records = [
        call
        for call in managed.log.console.log.call_args_list
        if call.args[2] == "gate.failed"
    ]
    assert len(records) == int(not debug)
    if records:
        assert records[0].args[0] == logging.ERROR
        assert "private provider error" not in str(records)
        assert "private invalid response" not in str(records)
    else:
        assert not managed.log.console.mock_calls


async def test_forced_branch_does_not_report_a_fabricated_model_plan(managed):
    message = managed.adapter.snapshot(admin_event("called directly"))
    await managed.storage.append(message)
    managed.controller.generate = AsyncMock()
    decision = await managed.controller.decide(message, True, False)
    assert decision.reply and decision.reason == "forced"
    managed.controller.generate.assert_not_awaited()
    await managed.log.flush()
    assert not any(
        row["event"] == "gate.complete"
        for row in entries(managed.log.directory / "runtime.log")
    )
