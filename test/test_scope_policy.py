"""Whitelist/blacklist routing and command exemptions through native events."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from humanization_test.core.astrbot_adapter import IdleEvent, ScopeFilter
from humanization_test.core.settings import Settings
from humanization_test.main import Humanization
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.core.pipeline.process_stage.stage import ProcessStage, StarRequestSubStage
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.regex import RegexFilter
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType


def set_policy(settings, all_sessions, action):
    settings.scope.update(
        all_sessions=all_sessions,
        sessions=[],
        manual_sessions=[],
        blacklist_sessions=["onebot:GroupMessage:123"],
        outside_action=action,
        blacklist_action=action,
    )


@pytest.mark.parametrize("all_sessions", [False, True])
@pytest.mark.parametrize("action", ["ignore", "listen", "drop"])
@pytest.mark.parametrize("private", [False, True])
def test_scope_policy_matches_exact_shared_and_manual_routes(
    config, all_sessions, action, private
):
    settings = Settings(config)
    set_policy(settings, all_sessions, action)
    route = "onebot:FriendMessage:42" if private else "onebot:GroupMessage:123"
    isolated = route if private else "onebot:GroupMessage:42_123"
    if all_sessions:
        settings.scope.update(blacklist_sessions=[], blacklist_manual_sessions=[route])
        expected = action
        unlisted = "active"
    else:
        settings.scope["manual_sessions"] = [route]
        expected = "active"
        unlisted = action
    assert settings.scope_action(isolated, route) == expected
    assert settings.selected(isolated, route) is (expected == "active")
    assert (
        settings.scope_action("other:FriendMessage:42", "other:FriendMessage:42")
        == unlisted
    )


@pytest.mark.parametrize("key", ["outside_action", "blacklist_action"])
def test_scope_rejects_unknown_action(config, key):
    config["scope"][key] = "unexpected"
    with pytest.raises(ValueError, match="Unknown scope action"):
        Settings(config)


@pytest.mark.parametrize("all_sessions", [False, True])
@pytest.mark.parametrize("action", ["ignore", "listen", "drop"])
@pytest.mark.parametrize("controller_enabled", [False, True])
async def test_ordinary_scope_actions_never_fall_through_to_models(
    plugin, all_sessions, action, controller_enabled
):
    set_policy(plugin.settings, all_sessions, action)
    plugin.settings.controller["enabled"] = controller_enabled
    plugin.adapter.can_reply = AsyncMock(return_value=True)
    plugin.controller.decide = AsyncMock()
    plugin.adapter.request = AsyncMock()
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    event = Event(direct=True)
    assert ScopeFilter().filter(event, {}) is (action != "ignore")
    if action != "ignore":
        await entry.prepare_input(event)
        if not event.is_stopped():
            await consume(plugin.observe(event))
            assert await consume(plugin.participate(event)) == []
    assert await plugin.storage.message_count(plugin.adapter.snapshot(event).scope) == (
        1 if action == "listen" else 0
    )
    assert event.is_stopped() is (action == "drop")
    if action == "listen":
        assert event.call_llm and not event.get_extra("humanization_claimed")
        await plugin.inject(event, ProviderRequest(prompt="unexpected native request"))
        assert event.is_stopped()
    if action == "ignore":
        assert not event.call_llm
    plugin.adapter.can_reply.assert_not_awaited()
    plugin.controller.decide.assert_not_awaited()
    plugin.adapter.request.assert_not_awaited()
    assert not plugin.scheduler.states


@pytest.mark.parametrize("all_sessions", [False, True])
@pytest.mark.parametrize("action", ["ignore", "listen", "drop"])
async def test_scope_never_blocks_matched_plugin_commands_or_their_llm_requests(
    plugin, monkeypatch, all_sessions, action
):
    set_policy(plugin.settings, all_sessions, action)
    plugin.controller.decide = AsyncMock()
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    calls = []

    async def command(event):
        yield ProviderRequest(prompt="request owned by the command plugin")

    handlers = []
    for name, callback, filters in (
        ("prepare_input", entry.prepare_input, []),
        ("observe", plugin.observe, []),
        ("command", command, [CommandFilter("demo")]),
        ("participate", plugin.participate, []),
    ):
        handlers.append(
            SimpleNamespace(
                handler_module_path="scope.test",
                handler_name=name,
                handler_full_name=f"scope.test.{name}",
                handler=callback,
                event_type=EventType.AdapterMessageEvent,
                event_filters=filters,
                extras_configs={},
            )
        )
    monkeypatch.setitem(
        star_map,
        "scope.test",
        SimpleNamespace(name="scope-test", display_name="Scope test"),
    )
    event = Event("demo", direct=True)
    event.is_at_or_wake_command = True
    event.set_extra("activated_handlers", handlers)

    async def agent(event):
        request = event.get_extra("provider_request")
        await plugin.inject(event, request)
        assert not event.is_stopped()
        calls.append(request.prompt)
        event._has_send_oper = True
        if False:
            yield

    stage = ProcessStage()
    stage.ctx = SimpleNamespace(astrbot_config={"provider_settings": {"enable": True}})
    stage.star_request_sub_stage = StarRequestSubStage()
    stage.agent_sub_stage = SimpleNamespace(process=agent)
    await consume(stage.process(event))
    assert calls == ["request owned by the command plugin"]
    assert not event.is_stopped()
    assert await plugin.storage.message_count(plugin.adapter.snapshot(event).scope) == 0
    plugin.controller.decide.assert_not_awaited()


async def test_regex_command_is_exempt_but_unknown_prefix_is_not(plugin):
    set_policy(plugin.settings, True, "drop")
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    event = Event("demo")
    event.set_extra(
        "activated_handlers", [SimpleNamespace(event_filters=[RegexFilter("demo")])]
    )
    await entry.prepare_input(event)
    assert not event.is_stopped()
    unknown = Event("/not-a-registered-command")
    await entry.prepare_input(unknown)
    assert unknown.is_stopped()


async def test_listening_command_recording_still_obeys_recorder_filter(plugin):
    set_policy(plugin.settings, True, "listen")
    plugin.settings.recorder["filter_commands"] = False
    event = Event("demo")
    event.set_extra(
        "activated_handlers", [SimpleNamespace(event_filters=[CommandFilter("demo")])]
    )
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    await entry.prepare_input(event)
    await consume(plugin.observe(event))
    await plugin.inject(event, ProviderRequest(prompt="command request"))
    assert not event.is_stopped() and not event.call_llm
    assert await plugin.storage.message_count(plugin.adapter.snapshot(event).scope) == 1


async def test_listening_skips_existing_summary_backlog_and_synthetic_turns(plugin):
    event = Event()
    message = plugin.adapter.snapshot(event)
    await plugin.storage.append(message)
    plugin.settings.recorder.update(summary_provider="summary", summary_every=1)
    set_policy(plugin.settings, True, "listen")
    plugin.summarizer.generate = AsyncMock()
    await plugin.summarizer.tick()
    plugin.summarizer.generate.assert_not_awaited()
    session = await plugin.storage.session(message.scope)
    idle = IdleEvent(plugin.context, event.platform_meta, session, plugin.generation)
    assert await consume(plugin.observe(idle)) == []
    assert idle.is_stopped()
    assert await plugin.storage.message_count(message.scope) == 1


async def test_listening_keeps_native_storage_and_commands_but_removes_native_llm_triggers(
    plugin,
):
    set_policy(plugin.settings, True, "listen")
    handlers = [
        SimpleNamespace(
            handler_module_path="astrbot.builtin_stars.astrbot.main",
            handler_name=name,
            event_filters=[],
        )
        for name in ("persist_group_message", "on_message", "handle_empty_mention")
    ]
    event = Event(direct=True)
    event.set_extra("activated_handlers", handlers)
    entry = object.__new__(Humanization)
    entry.runtime = plugin
    await entry.prepare_input(event)
    assert [handler.handler_name for handler in handlers] == ["persist_group_message"]
    assert event.call_llm and not event.is_stopped()


async def test_disabled_recorder_disables_scope_interception(plugin):
    set_policy(plugin.settings, True, "drop")
    plugin.settings.recorder["enabled"] = False
    assert not ScopeFilter().filter(Event(), {})
