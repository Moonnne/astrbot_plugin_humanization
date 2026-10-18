"""Per-chat decimal credits, bounded waiting and native queue ownership."""

import asyncio
import time
from datetime import datetime
from decimal import Decimal

from astrbot.api.message_components import At

from ...models.scheduling import ScheduleState, Ticket
from ..astrbot_adapter import ScheduledEvent


class Scheduler:
    """Own timing and lifecycle behind submit, claim, complete and reset.

    Args:
        settings: Validated plugin configuration.
        emit: Synchronous insertion into the native event queue.
        generation: Runtime identity rejecting events from previous reloads.
        log: Plugin logger.
        clock: Wall clock used with persisted reply timestamps and time periods.
        call_later: Optional fixed-clock timer implementation for tests.
    """

    def __init__(
        self, settings, emit, generation, log, clock=time.time, call_later=None
    ):
        self.settings = settings
        self.emit = emit
        self.generation = generation
        self.log = log
        self.clock = clock
        self.call_later = call_later
        self.states = {}
        self.closed = False

    def submit(self, event, message, session):
        """Count one newly recorded input and retain at most one pending snapshot.

        Args:
            event: Original event after other message handlers have had a chance.
            message: Newly stored human message.
            session: Storage cursor and latest completed-reply timestamp.
        """
        if self.closed:
            return
        state = self.states.setdefault(message.scope, ScheduleState())
        direct = any(
            isinstance(part, At) and str(part.qq) == message.self_id
            for part in event.get_messages()
        )
        mentioned = self.settings.mentioned(message.text, message.segments)
        forced = self.settings.forced(direct, mentioned)
        consumed = max(
            state.reviewed,
            state.queued.sequence if state.queued is not None else 0,
            state.active.sequence if state.active is not None else 0,
        )
        if not forced and session["last_seq"] <= consumed:
            return
        now = self.clock()
        activity = self.settings.effective_activity(
            message.private,
            direct,
            mentioned,
            datetime.fromtimestamp(now, self.settings.timezone),
        )
        state.idle_credit = Decimal(0)
        state.last_reply = max(state.last_reply, session["last_reply"])
        newer = session["last_seq"] > state.sequence
        state.sequence = max(state.sequence, session["last_seq"])
        if activity == 0 and not forced and not state.forced:
            # A zero-activity period discards ordinary pending work immediately.
            if state.pending is not None:
                state.pending.cleanup_temporary_local_files()
            state.pending = None
            state.credit = Decimal(0)
            state.due = False
            state.expedited = False
            self._arm(message.scope, state)
            return
        if state.pending is None:
            state.first_at = now
        if forced or (not state.forced and (newer or state.pending is None)):
            if state.pending is not None:
                state.pending.cleanup_temporary_local_files()
            state.pending = ScheduledEvent(event, message, self.generation)
        state.last_at = now
        state.forced = state.forced or forced
        state.expedited = state.expedited or direct or mentioned
        state.credit += Decimal(str(activity))
        if state.credit >= 1:
            state.due = True
            state.credit %= 1
        self.log.debug(
            "schedule.input",
            scope=message.scope,
            sequence=state.sequence,
            credit=str(state.credit),
            due=state.due,
            forced=state.forced,
        )
        self._arm(message.scope, state)

    def _arm(self, scope, state):
        """Replace the single timer using the current period and batch deadline.

        Args:
            scope: Canonical group or private-chat key.
            state: Current epoch's credits and pending snapshot.
        """
        if state.timer is not None:
            state.timer.cancel()
            state.timer = None
        if (
            self.closed
            or state.pending is None
            or state.queued is not None
            or state.active is not None
            or state.idle_queued
        ):
            return
        now = self.clock()
        event = state.pending
        message = event.get_extra("humanization_message")
        direct = any(
            isinstance(part, At) and str(part.qq) == message.self_id
            for part in event.get_messages()
        )
        activity = self.settings.effective_activity(
            message.private,
            direct,
            self.settings.mentioned(message.text, message.segments),
            datetime.fromtimestamp(now, self.settings.timezone),
        )
        if not state.forced and activity == 0:
            state.pending = None
            state.credit = Decimal(0)
            state.due = False
            state.forced = state.expedited = False
            event.cleanup_temporary_local_files()
            return
        cfg = self.settings.controller
        wait = (
            cfg["wait_min_seconds"]
            + (cfg["wait_max_seconds"] - cfg["wait_min_seconds"]) * (1 - activity) ** 2
        )
        deadline = state.first_at + wait
        target = (
            min(state.last_at + cfg["debounce_seconds"], deadline)
            if state.due or state.expedited
            else deadline
        )
        target = (
            now
            if state.forced
            else max(
                target, state.last_reply + cfg["cooldown_seconds"], state.backoff_until
            )
        )
        state.ready_at = target
        later = self.call_later or asyncio.get_running_loop().call_later
        state.timer = later(max(0, target - now), self._dispatch, scope, state.epoch)

    def _dispatch(self, scope, epoch):
        """Reserve one batch after rechecking its epoch and time-period settings.

        Args:
            scope: Canonical chat key retained by the timer.
            epoch: Epoch that created the timer, invalidated on reset.
        """
        state = self.states.get(scope)
        if (
            self.closed
            or state is None
            or state.epoch != epoch
            or state.pending is None
            or state.active is not None
            or state.queued is not None
            or state.idle_queued
        ):
            return
        state.timer = None
        # Re-evaluate time-period settings at the deadline, not only on arrival.
        self._arm(scope, state)
        if state.pending is None:
            return
        if state.timer is not None:
            # The recalculated deadline may have moved after a period change.
            if state.ready_at > self.clock():
                return
            state.timer.cancel()
            state.timer = None
        event = state.pending
        message = event.get_extra("humanization_message")
        direct = any(
            isinstance(part, At) and str(part.qq) == message.self_id
            for part in event.get_messages()
        )
        ticket = Ticket(
            scope,
            epoch,
            event,
            state.sequence,
            state.forced,
            direct,
            self.settings.mentioned(message.text, message.segments),
        )
        if state.forced or not state.due:
            state.credit = Decimal(0)
        state.pending = None
        state.forced = state.expedited = state.due = False
        state.queued = ticket
        event.set_extra(
            "humanization_scheduled", {"generation": self.generation, "ticket": ticket}
        )
        event.on_cleanup = lambda: self.complete(ticket, "skipped", False)
        self.emit(event)
        self.log.debug(
            "schedule.queued",
            scope=scope,
            through_seq=ticket.sequence,
            forced=ticket.forced,
        )

    def claim(self, event):
        """Accept only the current queue reservation and consume its input range.

        Args:
            event: Marked event delivered by the native pipeline.

        Returns:
            The exclusive batch ticket, or None for stale or already-replied work.
        """
        marker = event.get_extra("humanization_scheduled")
        if self.closed or marker["generation"] != self.generation:
            return None
        ticket = marker.get("ticket")
        state = self.states.get(ticket.scope) if ticket is not None else None
        if state is None or state.epoch != ticket.epoch or state.queued is not ticket:
            return None
        state.queued = None
        state.active = ticket
        state.reviewed = ticket.sequence
        if event.source._has_send_oper:
            self.complete(ticket, "skipped", False)
            return None
        return ticket

    def complete(self, ticket, outcome, delivered):
        """Consume this batch without consuming inputs arriving during its run.

        Args:
            ticket: Claimed or discarded native-queue batch.
            outcome: Semantic wait, model error, reply or skipped evaluation.
            delivered: Whether the native sending stage completed a reply.
        """
        state = self.states.get(ticket.scope)
        if (
            state is None
            or state.epoch != ticket.epoch
            or (state.active is not ticket and state.queued is not ticket)
        ):
            return
        state.reviewed = max(state.reviewed, ticket.sequence)
        state.active = state.queued = None
        if delivered:
            state.wait_streak = 0
            state.backoff_until = 0
            state.last_reply = self.clock()
        elif outcome == "semantic_wait":
            state.wait_streak += 1
            if state.wait_streak >= 2:
                state.backoff_until = self.clock() + min(
                    120, 10 * 2 ** min(state.wait_streak - 2, 4)
                )
        elif outcome == "error":
            state.wait_streak = 0
        self.log.debug(
            "schedule.complete",
            scope=ticket.scope,
            through_seq=ticket.sequence,
            outcome=outcome,
            delivered=delivered,
            wait_streak=state.wait_streak,
            backoff_until=state.backoff_until,
        )
        self._arm(ticket.scope, state)

    def idle_ready(self, scope, activity):
        state = self.states.setdefault(scope, ScheduleState())
        if (
            state.pending is not None
            or state.active is not None
            or state.queued is not None
            or state.idle_queued
        ):
            return False
        state.idle_credit += Decimal(str(activity)) * Decimal(
            str(self.settings.proactive["probability"])
        )
        if state.idle_credit < 1:
            return False
        state.idle_credit %= 1
        state.idle_queued = True
        return True

    def end_idle(self, scope, delivered=False):
        state = self.states.get(scope)
        if state is not None:
            if delivered:
                state.last_reply = self.clock()
                state.wait_streak = 0
                state.backoff_until = 0
            state.idle_queued = False
            self._arm(scope, state)

    def reset(self, scope):
        state = self.states.pop(scope, None)
        if state is None:
            return
        if state.timer is not None:
            state.timer.cancel()
        for event in (
            state.pending,
            state.queued.event if state.queued is not None else None,
        ):
            if event is not None:
                event.cleanup_temporary_local_files()

    def close(self):
        self.closed = True
        for scope in list(self.states):
            self.reset(scope)
