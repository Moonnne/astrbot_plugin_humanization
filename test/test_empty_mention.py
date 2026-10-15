"""Exercise the host's actual high-priority empty-mention handler."""

import copy
from sys import maxsize
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from humanization_test.main import Humanization
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.api.message_components import At, Plain
from astrbot.builtin_stars.astrbot import main as builtin_module
from astrbot.core.config.default import DEFAULT_CONFIG
from astrbot.core.pipeline.process_stage.stage import ProcessStage, StarRequestSubStage
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.star.star import star_map


@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("controlled", [True, False])
async def test_native_empty_mention_does_not_steal_controlled_input(
    plugin, monkeypatch, minimum, controlled
):
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["platform_settings"].update(
        empty_mention_waiting=True, empty_mention_waiting_need_reply=True
    )
    config["provider_ltm_settings"]["group_message_history_enable"] = True
    plugin.context.get_config = lambda **kw: config
    history = AsyncMock(return_value=SimpleNamespace(id=1))
    plugin.context.message_history_manager = SimpleNamespace(
        insert_message_chain=history
    )
    plugin.context.conversation_manager = SimpleNamespace(
        get_curr_conversation_id=AsyncMock(return_value="conversation"),
        get_conversation=AsyncMock(return_value=SimpleNamespace()),
    )
    plugin.settings.recorder["minimum_context_enabled"] = minimum
    plugin.settings.controller["enabled"] = controlled
    plugin.settings.controller["mode"] = "probability"
    # Disable evaluation so this test isolates ownership and the native waiter.
    plugin.settings.controller["force_at"] = False
    plugin.settings.controller.update(group=0, at_weight=0)
    plugin.settings.recorder["minimum_context_messages"] = 50
    builtin = object.__new__(builtin_module.Main)
    builtin.context = plugin.context
    waiters = []

    def waiter(timeout):
        waiters.append(timeout)

        def decorate(handler):
            async def wait(event):
                return None

            return wait

        return decorate

    monkeypatch.setattr(builtin_module, "session_waiter", waiter)

    def metadata(module, name, handler, priority):
        return SimpleNamespace(
            handler_module_path=module,
            handler_name=name,
            handler_full_name=f"{module}.{name}",
            handler=handler,
            event_filters=[],
            extras_configs={"priority": priority},
        )

    from astrbot.core.star.star_handler import EventType, star_handlers_registry

    registered = {
        h.handler_name: h
        for h in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent
        )
        if h.handler_module_path == Humanization.__module__
    }
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    handlers = [
        metadata(
            "humanization.test",
            "prepare_input",
            entry.prepare_input,
            registered["prepare_input"].extras_configs["priority"],
        ),
        metadata(
            "humanization.test",
            "observe",
            plugin.observe,
            registered["observe"].extras_configs["priority"],
        ),
        metadata(
            "astrbot.builtin_stars.astrbot.main",
            "handle_empty_mention",
            builtin.handle_empty_mention,
            maxsize - 1,
        ),
        metadata(
            "astrbot.builtin_stars.astrbot.main",
            "persist_group_message",
            builtin.persist_group_message,
            maxsize - 2,
        ),
        metadata("humanization.test", "participate", plugin.participate, -10000),
    ]
    handlers.sort(key=lambda h: -h.extras_configs["priority"])
    for handler in handlers:
        monkeypatch.setitem(
            star_map, handler.handler_module_path, SimpleNamespace(name="test")
        )

    event = Event("", direct=True)
    event.message_obj.message = [At(qq="999")]
    event.is_at_or_wake_command = True
    event.set_extra("activated_handlers", handlers)
    calls = []

    async def agent(event):
        request = event.get_extra("provider_request")
        await plugin.inject(event, request)
        if not event.is_stopped():
            calls.append(request)
            event._has_send_oper = True
        if False:
            yield

    stage = ProcessStage()
    stage.ctx = SimpleNamespace(astrbot_config=config)
    stage.star_request_sub_stage = StarRequestSubStage()
    stage.agent_sub_stage = SimpleNamespace(process=agent)
    await consume(stage.process(event))
    count = await plugin.storage.message_count(plugin.adapter.snapshot(event).scope)
    if controlled:
        assert count == 1
        assert waiters == []
        assert calls == []
        history.assert_awaited_once()
        recorded = history.call_args.kwargs["message_chain"].chain
        assert len(recorded) == 1 and isinstance(recorded[0], At)
    else:
        assert count == 0
        assert waiters == [60]
        assert len(calls) == 1


@pytest.mark.parametrize("prefix_only", [False, True])
async def test_native_collector_keeps_bare_wake_as_nonempty_input(plugin, prefix_only):
    conversation = SimpleNamespace(cid="test", history="[]")
    plugin.context.conversation_manager = SimpleNamespace(
        get_curr_conversation_id=AsyncMock(return_value="test"),
        get_conversation=AsyncMock(return_value=conversation),
    )
    event = Event("", direct=True)
    event.message_obj.message = [Plain("睦")] if prefix_only else [At(qq="999")]
    await consume(plugin.observe(event))
    request = await plugin.adapter.request(event)
    assert isinstance(request, ProviderRequest)
    assert request.prompt == ("睦" if prefix_only else "[@999]")
