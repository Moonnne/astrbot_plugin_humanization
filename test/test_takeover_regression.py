"""Native fallback must not bypass an enabled conversation's observation gate."""

from unittest.mock import AsyncMock

import pytest
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin
from test_native_delivery import native as native

from astrbot.core.provider.entities import ProviderRequest


@pytest.mark.parametrize("mode", ["probability", "scheduled"])
async def test_at_below_minimum_cannot_fall_back_when_reply_is_not_permitted(
    plugin, native, mode
):
    plugin.settings.controller["mode"] = mode
    plugin.settings.recorder.update(
        minimum_context_enabled=True, minimum_context_messages=50
    )
    plugin.adapter.can_reply = AsyncMock(return_value=False)
    plugin.controller.decide = AsyncMock()
    event = Event(direct=True)
    event.is_at_or_wake_command = True
    calls = []

    async def agent(event):
        calls.append(event)
        async for item in native.answer(
            event, text="？…@我但是不说话。\n\n想聊什么就说吧，我还没睡。"
        ):
            yield item

    await native.run(event, agent)
    assert await plugin.storage.message_count(plugin.adapter.snapshot(event).scope) == 1
    assert calls == [], "Native fallback bypassed Humanization's observation gate"
    assert event.sent == []
    plugin.controller.decide.assert_not_awaited()


async def test_controller_disabled_retains_native_at_reply(plugin, native):
    plugin.settings.controller["enabled"] = False
    plugin.settings.recorder["minimum_context_enabled"] = True
    event = Event(direct=True)
    event.is_at_or_wake_command = True

    async def agent(event):
        async for item in native.answer(event, text="native reply"):
            yield item

    await native.run(event, agent)
    assert len(event.sent) == 1


async def test_native_request_hook_blocks_unplanned_at_below_minimum(plugin):
    plugin.settings.recorder["minimum_context_enabled"] = True
    event = Event(direct=True)
    await consume(plugin.observe(event))
    assert event.get_extra("humanization_turn") is None
    request = ProviderRequest(prompt="hello", system_prompt="native persona")
    await plugin.inject(event, request)
    assert event.is_stopped()
    assert request.system_prompt == "native persona"


async def test_recorded_command_request_is_not_stopped_by_observation_gate(plugin):
    plugin.settings.recorder.update(minimum_context_enabled=True, filter_commands=False)
    event = Event("/other_plugin", direct=True)
    await consume(plugin.observe(event))
    assert event.get_extra("humanization_message") is not None
    await plugin.inject(event, ProviderRequest(prompt="command-owned request"))
    assert not event.is_stopped()


async def test_selected_group_gate_does_not_require_observer_to_have_run(plugin):
    plugin.settings.recorder["minimum_context_enabled"] = True
    event = Event("", direct=True)
    assert event.get_extra("humanization_message") is None
    await plugin.inject(event, ProviderRequest(prompt="bare mention"))
    assert event.is_stopped()
    assert await plugin.storage.message_count(plugin.adapter.snapshot(event).scope) == 0


async def test_request_without_observer_outside_selected_group_is_not_blocked(plugin):
    plugin.settings.recorder["minimum_context_enabled"] = True
    event = Event("", direct=True)
    event.message_obj.group_id = "456"
    event.unified_msg_origin = "onebot:GroupMessage:456"
    await plugin.inject(event, ProviderRequest(prompt="another group"))
    assert not event.is_stopped()


async def test_unobserved_command_keeps_its_native_request(plugin):
    plugin.settings.recorder["minimum_context_enabled"] = True
    event = Event("/other_plugin", direct=True)
    await plugin.inject(event, ProviderRequest(prompt="command-owned request"))
    assert not event.is_stopped()
