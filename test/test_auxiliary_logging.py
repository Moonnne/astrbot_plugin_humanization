"""Business outcomes and storage semantics remain intact after logging changes."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from controller_helpers import plan_json
from diary_helpers import model_change
from test_host_contract import plugin as plugin
from test_logging import entries
from test_management import admin_event
from test_management import managed as managed


@pytest.mark.parametrize("private", [False, True])
async def test_recorder_start_and_commit_count(managed, private):
    managed.settings.scope["all_sessions"] = True
    managed.settings.recorder.update(summary_provider="summary", summary_every=2)
    for number in range(1, 4):
        event = admin_event(f"private source {number}", private=private)
        event.message_obj.message_id = str(number)
        message = managed.adapter.snapshot(event)
        await managed.storage.append(message)
    managed.summarizer.generate = AsyncMock(return_value=model_change("diary topic", 1))
    await managed.summarizer.tick()
    await managed.log.flush()
    rows = entries(managed.log.directory / "humanization.log")
    started = next(row for row in rows if row["event"] == "summary.start")
    complete = next(row for row in rows if row["event"] == "summary.complete")
    scope = "onebot:FriendMessage:42" if private else "onebot:GroupMessage:123"
    assert scope in started["body"] and scope in complete["body"]
    assert (
        "message_count=3" in complete["body"] and "added_topics=1" in complete["body"]
    )
    assert "duration_seconds=" in complete["body"]
    assert (await managed.storage.session(message.scope))["cursor"] == 3
    assert "private source" not in str(rows)
    assert not managed.log.console.mock_calls


@pytest.mark.parametrize(
    "failure", [TimeoutError("provider failed"), ValueError("invalid response")]
)
async def test_recorder_failure_leaves_cursor_retryable(managed, failure):
    managed.settings.recorder.update(summary_provider="summary", summary_every=1)
    message = managed.adapter.snapshot(admin_event("private source"))
    await managed.storage.append(message)
    managed.summarizer.generate = AsyncMock(side_effect=failure)
    await managed.summarizer.tick()
    await managed.log.flush()
    rows = entries(managed.log.directory / "humanization.log")
    failed = next(row for row in rows if row["event"] == "summary.failed")
    assert "message_count=0" in failed["body"]
    assert "candidate_count=1" in failed["body"]
    assert type(failure).__name__ in failed["body"]
    assert (await managed.storage.session(message.scope))["cursor"] == 0
    assert not await managed.storage.diaries(message.scope)


@pytest.mark.parametrize("reply", [False, True])
async def test_controller_plan_and_outcome_are_unchanged(managed, reply):
    managed.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0
    )
    message = managed.adapter.snapshot(admin_event("private source"))
    await managed.storage.append(message)
    guidance = "keep this exact plan"
    managed.controller.generate = AsyncMock(
        return_value=plan_json(
            reply=reply, target=message.message_id, guidance=guidance
        )
    )
    decision = await managed.controller.decide(message, False, False)
    assert decision.reply is reply
    assert decision.intent == (guidance if reply else "")
    await managed.log.flush()
    rows = entries(managed.log.directory / "humanization.log")
    assert any(row["event"] == "gate.start" for row in rows)
    complete = next(row for row in rows if row["event"] == "gate.complete")
    assert f"action={'reply' if reply else 'wait'}" in complete["body"]
    assert "emotion=NEUTRAL" in complete["body"]
    assert "onebot:GroupMessage:123" in complete["body"]
    assert guidance not in str(rows)


@pytest.mark.parametrize("forced", [False, True])
async def test_controller_failure_keeps_fallback_policy(managed, forced):
    managed.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0
    )
    message = managed.adapter.snapshot(admin_event("private source"))
    await managed.storage.append(message)
    managed.controller.generate = AsyncMock(side_effect=TimeoutError("provider failed"))
    decision = await managed.controller.decide(message, forced, False)
    assert decision.reply is forced
    await managed.log.flush()
    rows = entries(managed.log.directory / "humanization.log")
    assert any(row["event"] == "gate.failed" for row in rows)
    assert not any(row["event"] == "gate.complete" for row in rows)


async def test_controller_cancellation_is_not_converted_to_reply(managed):
    managed.settings.controller.update(
        group=1, gate_provider="gate", cooldown_seconds=0
    )
    message = managed.adapter.snapshot(admin_event("private source"))
    await managed.storage.append(message)
    managed.controller.generate = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await managed.controller.decide(message, True, False)


async def test_background_crash_is_critical(managed):
    async def crash():
        raise RuntimeError("worker died")

    task = asyncio.create_task(crash())
    await asyncio.sleep(0)
    managed._background_done(task)
    raw = (managed.log.directory / "humanization.log").read_text(encoding="utf-8")
    assert "runtime.worker.stopped" in raw and "CRIT" in raw


async def test_forced_no_provider_does_not_fabricate_a_model_completion(managed):
    message = managed.adapter.snapshot(admin_event("direct"))
    await managed.storage.append(message)
    decision = await managed.controller.decide(message, True, False)
    assert decision.reply and decision.reason == "forced"
    await managed.log.flush()
    assert not any(
        row["event"] == "gate.complete"
        for row in entries(managed.log.directory / "humanization.log")
    )
