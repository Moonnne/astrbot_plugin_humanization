"""Read-only, administrator-scoped Recorder metadata and native info commands."""

import re
import time
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from humanization_test.main import Humanization
from test_host_contract import consume
from test_host_contract import plugin as plugin
from test_management import admin_event
from test_management import managed as managed

from astrbot.core.star.context import Context
from astrbot.core.star.star_handler import EventType, star_handlers_registry


@pytest.fixture
def named(managed):
    aliases = [
        SimpleNamespace(
            umo="onebot:GroupMessage:123", user_alias="测试群", auto_name="自动群名"
        ),
        SimpleNamespace(
            umo="onebot:GroupMessage:42_123", user_alias="成员会话", auto_name="测试群"
        ),
        SimpleNamespace(
            umo="onebot:FriendMessage:42", user_alias="管理员", auto_name="User"
        ),
    ]
    managed.context.get_db = lambda: SimpleNamespace(
        get_umo_aliases=AsyncMock(return_value=aliases)
    )
    managed.settings.recorder["summary_provider"] = "recorder-id"
    managed.settings.controller["gate_provider"] = "controller-id"
    managed.context.provider_manager = SimpleNamespace(
        inst_map={
            "recorder-id": SimpleNamespace(get_model=lambda: "RecorderModel"),
            "controller-id": SimpleNamespace(get_model=lambda: "ControllerModel"),
        }
    )
    managed.context.get_provider_by_id = Context.get_provider_by_id.__get__(
        managed.context
    )
    managed.context.llm_generate = AsyncMock()
    managed.controller.generate = AsyncMock()
    managed.summarizer.generate = AsyncMock()
    return managed


async def seed(runtime, private=False, group="123", platform="onebot"):
    event = admin_event("private source content", private=private, group=group)
    event.platform_meta.id = platform
    event.session.platform_id = platform
    message = runtime.adapter.snapshot(event)
    for seq in range(1, 7):
        await runtime.storage.append(
            replace(
                message, message_id=str(seq), direction="out" if seq in (3, 5) else "in"
            )
        )
    yesterday = (
        datetime.now(runtime.settings.timezone).date() - timedelta(days=1)
    ).isoformat()
    await runtime.storage.commit_summary(
        message.scope, yesterday, "private older diary", 2, 2, time.time() - 3600
    )
    await runtime.storage.commit_summary(
        message.scope, message.day, "private current diary", 4, 3, time.time()
    )
    return message


@pytest.mark.parametrize("private", [False, True])
async def test_current_scope_info_has_six_ordered_lines_and_never_changes_data(
    named, private
):
    message = await seed(named, private)
    before = {
        table: await named.storage.rows(f"SELECT * FROM {table}")
        for table in ("sessions", "messages", "daily_summaries", "reply_runs")
    }
    caller = admin_event("/hum info", private=private)
    lines = (await named.admin.info(caller)).splitlines()
    assert len(lines) == 6
    assert lines[0] == (
        "[私聊]管理员 : onebot:FriendMessage:42"
        if private
        else "[群聊]测试群 : onebot:GroupMessage:123"
    )
    assert lines[1] == "聊天记录：500/6（上限/已有条数）"
    assert f"{message.day}@seq4（版本生成时间：" in lines[2]
    assert "日记总数：2" in lines[2] and "摘要进度：50/1" in lines[2]
    assert lines[3] == "Recorder 模型：RecorderModel（recorder-id）"
    assert lines[4] == "Controller 模型：ControllerModel（controller-id）"
    assert re.fullmatch(
        r"查询时间：\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+0800", lines[5]
    )
    assert "private source" not in "\n".join(
        lines
    ) and "private current diary" not in "\n".join(lines)
    for table, rows in before.items():
        assert await named.storage.rows(f"SELECT * FROM {table}") == rows
    named.context.llm_generate.assert_not_awaited()
    named.controller.generate.assert_not_awaited()
    named.summarizer.generate.assert_not_awaited()


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("private_caller", [False, True])
async def test_explicit_group_info_accepts_member_umos_from_any_admin_chat(
    named, isolated, private_caller
):
    await seed(named)
    umo = "onebot:GroupMessage:42_123" if isolated else "onebot:GroupMessage:123"
    caller = admin_event("/hum info " + umo, private=private_caller, group="456")
    response = await named.admin.info(caller, umo)
    assert response.splitlines()[0] == "[群聊]测试群 : onebot:GroupMessage:123"
    assert "聊天记录：500/6" in response


async def test_current_member_scope_uses_whole_group_and_member_alias_when_needed(
    named,
):
    await seed(named)
    named.context.get_db = lambda: SimpleNamespace(
        get_umo_aliases=AsyncMock(
            return_value=[
                SimpleNamespace(
                    umo="onebot:GroupMessage:42_123",
                    user_alias="",
                    auto_name="群内名称",
                ),
            ]
        )
    )
    caller = admin_event("/hum info")
    caller.session.session_id = "43_123"
    response = await named.admin.info(caller)
    assert response.splitlines()[0] == "[群聊]群内名称 : onebot:GroupMessage:123"
    assert "500/6" in response


async def test_explicit_private_and_other_platform_info_use_the_target_scope(named):
    await seed(named, private=True)
    other = await seed(named, group="456", platform="otherbot")
    caller = admin_event("/hum info")
    private = await named.admin.info(caller, "onebot:FriendMessage:42")
    assert private.splitlines()[0] == "[私聊]管理员 : onebot:FriendMessage:42"
    response = await named.admin.info(caller, other.umo)
    assert response.splitlines()[0] == "[群聊]群 456 : otherbot:GroupMessage:456"
    assert "500/6" in response


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("specified", [False, True])
async def test_empty_info_distinguishes_unselected_scope_and_selected_empty_scope(
    named, enabled, specified
):
    named.settings.scope["sessions"] = ["onebot:GroupMessage:123"] if enabled else []
    caller = admin_event("/hum info")
    response = await named.admin.info(
        caller, "onebot:GroupMessage:123" if specified else ""
    )
    lines = response.splitlines()
    assert lines[0] == "[群聊]测试群 : onebot:GroupMessage:123"
    assert lines[1] == (
        ("指定会话无记录" if specified else "当前会话无记录")
        if enabled
        else "会话未启用插件"
    )
    assert len(lines) == 3 and lines[-1].startswith("查询时间：")
    assert not await named.storage.rows("SELECT * FROM sessions")


async def test_recorder_disabled_empty_scope_reports_plugin_not_enabled(named):
    named.settings.recorder["enabled"] = False
    assert "会话未启用插件" in await named.admin.info(admin_event("/hum info"))


@pytest.mark.parametrize(
    "umo",
    ["invalid", "onebot:OtherMessage:123", ":GroupMessage:123", "onebot:GroupMessage:"],
)
async def test_info_rejects_invalid_routes(named, umo):
    response = await named.admin.info(admin_event("/hum info", private=True), umo)
    assert "格式错误" in response or "仅支持" in response
    assert not await named.storage.rows("SELECT * FROM sessions")


async def test_rolled_rows_and_pending_summary_counts_use_different_units(named):
    await seed(named)
    named.storage.retention = 4
    named.settings.recorder["retention"] = 4
    await named.storage.trim()
    response = await named.admin.info(admin_event("/hum info"))
    assert "聊天记录：4/4" in response
    assert "摘要进度：50/1" in response


async def test_diary_only_scope_is_queryable_after_today_reset(named):
    message = await seed(named)
    await named.reset_scope(message, message.day)
    response = await named.admin.info(
        admin_event("/hum info", private=True), message.umo
    )
    assert "聊天记录：500/0" in response and "日记总数：1" in response
    assert "摘要进度：50/0" in response and "@seq2" in response


async def test_info_handles_missing_models_and_no_diary_without_inventing_metadata(
    named,
):
    message = named.adapter.snapshot(admin_event("ordinary"))
    await named.storage.append(message)
    named.settings.recorder["summary_provider"] = ""
    named.settings.controller["gate_provider"] = "missing-provider"
    response = await named.admin.info(admin_event("/hum info"))
    assert "现行日记版本：暂无日记；日记总数：0；摘要进度：50/1" in response
    assert "Recorder 模型：未配置" in response
    assert "Controller 模型：不可用（missing-provider）" in response


@pytest.mark.parametrize("enabled,admin", [(False, True), (True, False)])
async def test_info_access_is_silent_and_never_reads_storage_or_names(
    named, enabled, admin
):
    named.settings.management["enabled"] = enabled
    caller = admin_event("/hum info")
    if not admin:
        caller.role = "member"
    named.storage.rows = AsyncMock()
    named.storage.reset_targets = AsyncMock()
    named.context.get_db = Mock()
    assert await named.admin.info(caller, "onebot:GroupMessage:123") == ""
    named.storage.rows.assert_not_awaited()
    named.storage.reset_targets.assert_not_awaited()
    named.context.get_db.assert_not_called()


@pytest.mark.parametrize("specified", [False, True])
async def test_native_info_parser_and_management_guard_preserve_db_and_reset_request(
    named, specified
):
    message = await seed(named)
    await named.admin.request_reset(admin_event("request", private=True), "all")
    pending = dict(named.admin.pending)
    event = admin_event("hum info" + (" " + message.umo if specified else ""))
    event.is_at_or_wake_command = True
    handler = next(
        entry
        for entry in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent
        )
        if entry.handler_module_path == "humanization_test.main"
        and entry.handler_name == "info"
    )
    assert all(rule.filter(event, {}) for rule in handler.event_filters)
    instance = Humanization.__new__(Humanization)
    instance.runtime = named
    await instance.management_guard(event)
    await consume(instance.observe(event))
    results = await consume(instance.info(event, **event.get_extra("parsed_params")))
    assert len(results) == 1 and len(results[0].get_plain_text().splitlines()) == 6
    assert event.call_llm and event.is_stopped()
    assert len(await named.storage.rows("SELECT * FROM messages")) == 6
    assert named.admin.pending == pending
    named.context.conversation_manager.new_conversation.assert_not_awaited()
