"""Fixed-clock scheduling policy and native event lifecycle contracts."""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from humanization_test.core.astrbot_adapter import InternalEventFilter, ScheduledEvent
from humanization_test.core.controller.scheduler import Scheduler
from humanization_test.core.settings import Settings
from test_host_contract import Event, consume, replay
from test_host_contract import plugin as plugin

from astrbot.api.message_components import Image
from astrbot.core.platform.message_type import MessageType
from astrbot.core.provider.entities import LLMResponse, ProviderRequest
from astrbot.core.star.star_handler import EventType, star_handlers_registry


@dataclass
class Timer:
    deadline: float
    callback: object
    args: tuple
    cancelled: bool = False

    def cancel(self):
        self.cancelled = True


class Clock:
    def __init__(self, now=100):
        self.now = now
        self.timers = []

    def __call__(self):
        return self.now

    def later(self, delay, callback, *args):
        timer = Timer(self.now + delay, callback, args)
        self.timers.append(timer)
        return timer

    def advance(self, seconds):
        target = self.now + seconds
        while True:
            ready = [
                timer
                for timer in self.timers
                if not timer.cancelled and timer.deadline <= target
            ]
            if not ready:
                break
            timer = min(ready, key=lambda item: item.deadline)
            self.timers.remove(timer)
            self.now = timer.deadline
            timer.callback(*timer.args)
        self.now = target


@pytest.fixture
def policy(config, log):
    config["controller"].update(
        mode="scheduled", group=0.1, cooldown_seconds=0, debounce_seconds=0
    )
    settings = Settings(config)
    clock = Clock()
    emitted = []
    scheduler = Scheduler(
        settings, emitted.append, "generation", log, clock, clock.later
    )
    from humanization_test.core.astrbot_adapter import AstrBotAdapter

    adapter = AstrBotAdapter(None, settings, log)
    sequence = 0

    def submit(text="ordinary message", direct=False, sender="42", isolated=False):
        nonlocal sequence
        sequence += 1
        event = Event(text, direct=direct, sender=sender, message_id=str(sequence))
        if isolated:
            event.session_id = sender + "_123"
        message = adapter.snapshot(event)
        scheduler.submit(event, message, {"last_seq": sequence, "last_reply": 0})
        return event, message

    yield SimpleNamespace(
        settings=settings,
        scheduler=scheduler,
        clock=clock,
        emitted=emitted,
        submit=submit,
    )
    scheduler.close()


def test_tenth_point_one_input_meets_quota_exactly(policy):
    for _ in range(9):
        _, message = policy.submit()
        policy.clock.advance(0)
    assert not policy.emitted
    assert policy.scheduler.states[message.scope].credit == Decimal("0.9")
    policy.submit()
    policy.clock.advance(0)
    assert len(policy.emitted) == 1
    assert policy.scheduler.states[message.scope].credit == 0


def test_point_eight_keeps_fractional_frequency_instead_of_rounding(policy):
    policy.settings.controller["group"] = 0.8
    evaluated = []
    for index in range(1, 8):
        policy.submit()
        policy.clock.advance(0)
        if policy.emitted:
            ticket = policy.scheduler.claim(policy.emitted.pop(0))
            evaluated.append(index)
            policy.scheduler.complete(ticket, "reply", True)
    assert evaluated == [2, 3, 4, 5, 7]


def test_low_traffic_wait_consumes_once_without_new_messages(policy):
    policy.submit()
    policy.clock.advance(49.54)
    assert not policy.emitted
    policy.clock.advance(0.02)
    ticket = policy.scheduler.claim(policy.emitted.pop())
    policy.scheduler.complete(ticket, "error", False)
    policy.clock.advance(1000)
    assert not policy.emitted
    assert policy.scheduler.states[ticket.scope].credit == 0


def test_sustained_burst_has_bounded_debounce_and_no_request_backlog(policy):
    policy.settings.controller.update(
        group=1, debounce_seconds=10, wait_min_seconds=5, wait_max_seconds=5
    )
    for _ in range(5):
        policy.submit()
        policy.clock.advance(1)
    assert len(policy.emitted) == 1
    ticket = policy.scheduler.claim(policy.emitted.pop())
    assert ticket.sequence == 5
    policy.scheduler.complete(ticket, "reply", True)
    policy.clock.advance(30)
    assert not policy.emitted


def test_zero_activity_and_period_transition_do_not_dispatch(policy):
    policy.submit()
    policy.settings.controller["group"] = 0
    policy.clock.advance(60)
    assert not policy.emitted
    policy.submit()
    policy.clock.advance(60)
    assert not policy.emitted


def test_pending_wait_recalculates_across_time_periods(policy):
    local = datetime(2026, 10, 14, 22, 59, 50, tzinfo=policy.settings.timezone)
    policy.clock.now = local.timestamp()
    policy.settings.controller["group"] = 0.2
    policy.settings.periods = [
        SimpleNamespace(start=23 * 60, end=8 * 60, group=0, private=0)
    ]
    policy.submit()
    policy.clock.advance(60)
    assert not policy.emitted


def test_name_without_force_shortens_wait_but_still_needs_gate(policy):
    policy.settings.controller.update(
        names=["睦"], force_mention=False, mention_weight=0.1, debounce_seconds=2
    )
    policy.submit("睦，你觉得呢")
    policy.clock.advance(2)
    ticket = policy.scheduler.claim(policy.emitted.pop())
    assert ticket.mentioned and not ticket.forced


def test_force_bypasses_zero_activity_cold_and_wait_backoff(policy):
    policy.settings.controller.update(group=0, force_at=True, cooldown_seconds=100)
    _, message = policy.submit(direct=True)
    policy.scheduler.states[message.scope].backoff_until = 1000
    policy.clock.advance(0)
    ticket = policy.scheduler.claim(policy.emitted.pop())
    assert ticket.forced
    policy.scheduler.complete(ticket, "reply", True)
    assert policy.scheduler.states[message.scope].backoff_until == 0
    policy.clock.advance(1000)
    assert not policy.emitted


def test_wait_backoff_is_bounded_and_forced_inputs_can_bypass_it(policy):
    policy.settings.controller["group"] = 1
    intervals = []
    for _ in range(7):
        policy.submit()
        state = next(iter(policy.scheduler.states.values()))
        policy.clock.advance(max(0, state.backoff_until - policy.clock()))
        ticket = policy.scheduler.claim(policy.emitted.pop())
        policy.scheduler.complete(ticket, "semantic_wait", False)
        intervals.append(
            state.backoff_until - policy.clock() if state.wait_streak >= 2 else 0
        )
    assert intervals == [0, 10, 20, 40, 80, 120, 120]
    policy.submit(direct=True)
    policy.clock.advance(0)
    ticket = policy.scheduler.claim(policy.emitted.pop())
    policy.scheduler.complete(ticket, "reply", True)
    assert state.wait_streak == 0 and state.backoff_until == 0


def test_inputs_during_active_turn_form_a_separate_batch_and_keep_member_route(policy):
    policy.settings.controller["group"] = 1
    policy.submit(sender="42", isolated=True)
    policy.clock.advance(0)
    first = policy.scheduler.claim(policy.emitted.pop())
    policy.submit(sender="43", isolated=True)
    policy.clock.advance(0)
    assert not policy.emitted
    policy.scheduler.complete(first, "reply", True)
    policy.clock.advance(0)
    second = policy.scheduler.claim(policy.emitted.pop())
    assert first.scope == second.scope and second.sequence == 2
    assert first.event.unified_msg_origin == "onebot:GroupMessage:42_123"
    assert second.event.unified_msg_origin == "onebot:GroupMessage:43_123"


def test_out_of_order_eligible_inputs_keep_latest_target_and_do_not_repeat_reviewed_input(
    policy,
):
    from humanization_test.core.astrbot_adapter import AstrBotAdapter

    adapter = AstrBotAdapter(None, policy.settings, policy.scheduler.log)
    first = Event("older", message_id="first")
    second = Event("newer", message_id="second")
    old_message = adapter.snapshot(first)
    new_message = adapter.snapshot(second)
    policy.settings.controller["group"] = 0.5
    policy.scheduler.submit(second, new_message, {"last_seq": 2, "last_reply": 0})
    policy.scheduler.submit(first, old_message, {"last_seq": 1, "last_reply": 0})
    policy.clock.advance(0)
    ticket = policy.scheduler.claim(policy.emitted.pop())
    assert ticket.sequence == 2 and ticket.event.message_obj.message_id == "second"
    policy.scheduler.complete(ticket, "reply", True)
    policy.scheduler.submit(first, old_message, {"last_seq": 1, "last_reply": 0})
    policy.clock.advance(100)
    assert not policy.emitted


def test_queue_discard_and_reset_release_pending_work_without_replaying_history(policy):
    policy.settings.controller["group"] = 1
    _, message = policy.submit()
    policy.clock.advance(0)
    old = policy.emitted.pop()
    policy.submit()
    old.cleanup_temporary_local_files()
    policy.clock.advance(0)
    assert len(policy.emitted) == 1
    stale = policy.emitted.pop()
    policy.scheduler.reset(message.scope)
    assert policy.scheduler.claim(stale) is None
    policy.clock.advance(1000)
    assert not policy.emitted


def test_scheduled_idle_uses_decimal_checks_and_blocks_duplicate_queueing(policy):
    policy.settings.proactive["probability"] = 0.1
    assert not any(policy.scheduler.idle_ready("scope", 0.1) for _ in range(99))
    assert policy.scheduler.idle_ready("scope", 0.1)
    assert not policy.scheduler.idle_ready("scope", 1)
    policy.scheduler.end_idle("scope", delivered=True)
    assert policy.scheduler.states["scope"].last_reply == policy.clock()


async def test_runtime_batches_only_new_valid_inputs_and_uses_snapshot_cutoff(plugin):
    plugin.settings.controller.update(
        mode="scheduled", group=1, force_at=False, cooldown_seconds=0
    )
    queued = asyncio.Queue()
    plugin.context.get_event_queue = lambda: queued
    clock = Clock(time.time())
    plugin.scheduler.clock = clock
    plugin.scheduler.call_later = clock.later
    source = Event("first", message_id="first")
    await consume(plugin.observe(source))
    assert await consume(plugin.participate(source)) == []
    clock.advance(0)
    scheduled = queued.get_nowait()
    await consume(plugin.observe(Event("/command", message_id="command")))
    await consume(plugin.observe(Event("first", message_id="first")))
    assert len(await plugin.storage.rows("SELECT * FROM messages")) == 1
    gate = AsyncMock(return_value='{"action":"wait","intent":""}')
    plugin.settings.controller["gate_provider"] = "gate"
    plugin.controller.generate = gate
    assert await consume(plugin.observe(scheduled)) == []
    scheduled.cleanup_temporary_local_files()
    assert scheduled.is_stopped()
    assert len(await plugin.storage.rows("SELECT * FROM messages")) == 1
    assert json.loads(gate.call_args.args[2])["target"] == "first"
    clock.advance(1000)
    assert queued.empty()


async def test_force_scheduled_turn_preserves_native_reply_and_clears_state(plugin):
    plugin.settings.controller.update(mode="scheduled", group=0, force_at=True)
    queued = asyncio.Queue()
    plugin.context.get_event_queue = lambda: queued
    clock = Clock(time.time())
    plugin.scheduler.clock = clock
    plugin.scheduler.call_later = clock.later
    source = Event(direct=True)
    await consume(plugin.observe(source))
    await consume(plugin.participate(source))
    clock.advance(0)
    event = queued.get_nowait()
    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))
    generator = plugin.observe(event)
    await anext(generator)
    await plugin.validate(
        event, LLMResponse(role="assistant", completion_text="你好$嗯")
    )
    await replay(plugin, event, generator)
    assert [chain.get_plain_text() for chain in source.sent] == ["你好", "嗯"]
    assert event.is_stopped()
    state = next(iter(plugin.scheduler.states.values()))
    assert state.active is None and state.queued is None
    assert event.get_extra("humanization_turn") is None


async def test_queued_cutoff_excludes_inputs_arriving_before_gate_starts(plugin):
    plugin.settings.controller.update(
        mode="scheduled",
        group=1,
        force_at=False,
        cooldown_seconds=0,
        gate_provider="gate",
    )
    queue = asyncio.Queue()
    plugin.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    plugin.scheduler.clock = clock
    plugin.scheduler.call_later = clock.later
    first = Event("first only", message_id="first")
    await consume(plugin.observe(first))
    await consume(plugin.participate(first))
    clock.advance(0)
    first_event = queue.get_nowait()
    second = Event("future input", message_id="second")
    await consume(plugin.observe(second))
    await consume(plugin.participate(second))
    generate = AsyncMock(return_value='{"action":"wait","intent":""}')
    plugin.controller.generate = generate
    await consume(plugin.observe(first_event))
    payload = json.loads(generate.call_args.args[2])
    assert [row["message_id"] for row in payload["context"]["messages"]] == ["first"]
    clock.advance(0)
    second_event = queue.get_nowait()
    await consume(plugin.observe(second_event))
    assert json.loads(generate.call_args.args[2])["target"] == "second"
    clock.advance(1000)
    assert queue.empty()


async def test_reset_invalidates_scheduled_timer_and_queued_event(plugin):
    plugin.settings.controller.update(mode="scheduled", group=1, force_at=False)
    queue = asyncio.Queue()
    plugin.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    plugin.scheduler.clock = clock
    plugin.scheduler.call_later = clock.later
    plugin.context.conversation_manager = SimpleNamespace(
        get_conversations=AsyncMock(return_value=[]),
        get_curr_conversation_id=AsyncMock(return_value=None),
        new_conversation=AsyncMock(return_value="new"),
    )
    source = Event()
    await consume(plugin.observe(source))
    await consume(plugin.participate(source))
    clock.advance(0)
    stale = queue.get_nowait()
    message = source.get_extra("humanization_message")
    await plugin.reset_scope(message, None)
    assert await consume(plugin.observe(stale)) == []
    assert stale.is_stopped()
    assert message.scope not in plugin.scheduler.states
    assert not await plugin.storage.rows("SELECT * FROM messages")


def test_snapshot_transfers_temporary_media_ownership_and_preserves_raw_input(
    policy, tmp_path
):
    source = Event("Bot Bot hello")
    source.message_str = "Bot hello"
    path = tmp_path / "owned-image.png"
    path.write_bytes(b"temporary image")
    source.track_temporary_local_file(str(path))
    source.message_obj.message.append(Image(file=str(path)))
    from humanization_test.core.astrbot_adapter import AstrBotAdapter

    message = AstrBotAdapter(None, policy.settings, policy.scheduler.log).snapshot(
        source
    )
    event = ScheduledEvent(source, message, "generation")
    source.cleanup_temporary_local_files()
    assert path.exists()
    assert event.message_str == "Bot Bot hello"
    assert event.get_messages()[-1].file == str(path)
    event.cleanup_temporary_local_files()
    assert not path.exists()


def test_name_and_alias_identity_and_independent_force_option(config):
    config["controller"].update(
        robot_name="若叶睦", names=["睦", "Mutsumi"], at_weight=0.5
    )
    settings = Settings(config)
    assert settings.controller["force_at"] is True
    assert settings.mentioned("若叶睦，你怎么看")
    assert settings.mentioned("mutsumi hi")
    assert not settings.mentioned("NotMutsumiWord")
    settings.controller["at_weight"] = 0
    assert settings.forced(True, False)
    settings.controller["force_at"] = False
    settings.controller["at_weight"] = 1
    assert not settings.forced(True, False)


async def test_weight_one_without_force_still_calls_semantic_gate(plugin):
    plugin.settings.controller.update(
        force_at=False, at_weight=1, group=0, gate_provider="gate"
    )
    source = Event(direct=True)
    await consume(plugin.observe(source))
    generate = AsyncMock(return_value='{"action":"wait","intent":""}')
    plugin.controller.generate = generate
    decision = await plugin.controller.decide(
        source.get_extra("humanization_message"), True, False
    )
    assert not decision.reply and decision.reason == "semantic_wait"
    generate.assert_awaited_once()


async def test_name_force_is_independent_of_at_weight_and_semantic_gate(plugin):
    plugin.settings.controller.update(
        force_mention=True, names=["睦"], group=0, mention_weight=0, at_weight=0
    )
    source = Event("睦，你好")
    await consume(plugin.observe(source))
    generate = AsyncMock()
    plugin.controller.generate = generate
    decision = await plugin.controller.decide(
        source.get_extra("humanization_message"), False, True
    )
    assert decision.reply and decision.reason == "forced"
    generate.assert_not_awaited()


@pytest.mark.parametrize("private", [False, True])
def test_frequency_hints_and_wait_validation(config, private):
    config["controller"]["mode"] = "scheduled"
    settings = Settings(config)
    settings.controller["private" if private else "group"] = 0.5
    hint = settings.frequency_hint(
        settings.activity(private, datetime.now(settings.timezone))
    )
    assert "每2.00条" in hint
    assert "19秒" in hint
    assert "合并窗口" in settings.frequency_hint(1)
    assert "不评估" in settings.frequency_hint(0)
    settings.controller["mode"] = "probability"
    assert "50%" in settings.frequency_hint(0.5)
    config["controller"].update(wait_min_seconds=60, wait_max_seconds=5)
    with pytest.raises(ValueError, match="minimum scheduling wait"):
        Settings(config)


def test_private_senders_have_separate_credits_and_routes(policy):
    from humanization_test.core.astrbot_adapter import AstrBotAdapter

    policy.settings.controller["private"] = 0.5
    adapter = AstrBotAdapter(None, policy.settings, policy.scheduler.log)
    for index, sender in enumerate(("42", "43", "42"), start=1):
        event = Event(sender=sender, message_id=str(index))
        event.message_obj.type = MessageType.FRIEND_MESSAGE
        event.message_obj.group_id = ""
        event.session.message_type = MessageType.FRIEND_MESSAGE
        event.session.session_id = sender
        event.unified_msg_origin = str(event.session)
        message = adapter.snapshot(event)
        policy.scheduler.submit(event, message, {"last_seq": index, "last_reply": 0})
        policy.clock.advance(0)
    assert len(policy.scheduler.states) == 2
    assert len(policy.emitted) == 1
    event = policy.emitted[0]
    assert (
        event.is_private_chat()
        and event.unified_msg_origin == "onebot:FriendMessage:42"
    )


def test_close_rejects_queued_events_and_clears_pending_snapshots(policy):
    policy.settings.controller["group"] = 1
    policy.submit()
    policy.clock.advance(0)
    stale = policy.emitted.pop()
    policy.submit()
    policy.scheduler.close()
    assert not policy.scheduler.states
    assert policy.scheduler.claim(stale) is None
    assert stale.source is None
    policy.clock.advance(1000)
    assert not policy.emitted


def test_discarded_native_queue_batch_is_consumed_before_late_submission(policy):

    policy.settings.controller["group"] = 1
    source, message = policy.submit()
    policy.clock.advance(0)
    event = policy.emitted.pop()
    event.cleanup_temporary_local_files()
    policy.scheduler.submit(source, message, {"last_seq": 1, "last_reply": 0})
    policy.clock.advance(0)
    assert not policy.emitted
    assert policy.scheduler.states[message.scope].reviewed == 1


async def test_gate_prompt_contains_stable_identity_but_keeps_expression_separate(
    plugin,
):
    plugin.settings.controller.update(robot_name="若叶睦", names=["睦", "Mutsumi"])
    prompt = await plugin.prompts.gate(False)
    assert '"name":"若叶睦"' in prompt and '"aliases":["睦","Mutsumi"]' in prompt
    assert await plugin.prompts.fragment("expression") not in prompt


def test_internal_handler_precedes_native_incoming_recorders():
    from sys import maxsize

    from humanization_test.main import Humanization

    handlers = star_handlers_registry.get_handlers_by_event_type(
        EventType.AdapterMessageEvent, only_activated=False
    )
    guard = next(
        handler
        for handler in handlers
        if handler.handler_module_path == "humanization_test.main"
        and handler.handler is Humanization.scheduled_event
    )
    assert guard.extras_configs["priority"] > maxsize
    assert not InternalEventFilter().filter(Event(), {})
