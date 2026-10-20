"""Exercise view endpoints through the host request context and real SQLite."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from controller_helpers import plan_data
from diary_helpers import topic_change
from humanization_test.core.dashboard import Dashboard
from starlette.requests import Request
from test_host_contract import Event
from test_host_contract import plugin as plugin

from astrbot.api import AstrBotConfig
from astrbot.api.star import Context
from astrbot.api.web import PluginRequest, bind_request_context


async def invoke(handler, *, query=None, body=None, username="admin"):
    data = json.dumps(body).encode() if body is not None else b""

    async def receive():
        return {"type": "http.request", "body": data, "more_body": False}

    raw = Request(
        {
            "type": "http",
            "method": "POST" if body is not None else "GET",
            "path": "/api/v1/plugins/extensions/astrbot_plugin_humanization/test",
            "headers": [(b"content-type", b"application/json")],
            "query_string": urlencode(query or {}).encode(),
            "scheme": "http",
            "server": ("test", 80),
            "client": ("test", 123),
        },
        receive,
    )
    with bind_request_context(PluginRequest(raw, username=username)):
        result = await handler()
    return result.status_code, json.loads(result.body)


@pytest.fixture
async def dashboard(plugin, tmp_path, config):
    plugin.context.get_db = lambda: SimpleNamespace(
        get_umo_aliases=AsyncMock(return_value=[])
    )
    plugin.context.get_platform_inst = lambda platform_id: None
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "_conf_schema.json").read_text(
            encoding="utf-8"
        )
    )
    saved = AstrBotConfig(str(tmp_path / "panel.json"), schema=schema)
    saved.save_config(config)
    context = SimpleNamespace(
        get_all_providers=lambda: [],
        persona_manager=SimpleNamespace(get_all_personas=AsyncMock(return_value=[])),
        get_llm_tool_manager=lambda: SimpleNamespace(func_list=[]),
        get_all_stars=lambda: [SimpleNamespace(name=Dashboard.plugin_name)],
        _star_manager=SimpleNamespace(reload=AsyncMock(return_value=(True, None))),
        registered_web_apis=[],
    )
    context.register_web_api = lambda *args: Context.register_web_api(context, *args)
    view = Dashboard(SimpleNamespace(runtime=plugin, config=saved, context=context))
    for index, text in enumerate(
        ["天气很好", "<script>alert(1)</script>", "散步回来"], 1
    ):
        message = plugin.adapter.snapshot(Event(text, message_id=str(index)))
        await plugin.storage.append(message)
    await plugin.storage.commit_summary(
        message.scope, message.day, [topic_change("讨论天气")], 3, 3, message.sent_at
    )
    await plugin.storage.record_decision(
        message.scope,
        plan_data(),
        message.sent_at,
        3,
        message.sent_at,
        "message",
        False,
    )
    return view


@pytest.mark.parametrize("category", ["messages", "decisions", "topics", "diaries"])
async def test_browse_parses_json_and_scopes_data(dashboard, category):
    status, result = await invoke(
        dashboard.records, query={"category": category, "limit": 1}
    )
    assert status == 200 and len(result["items"]) == 1
    row = result["items"][0]
    assert row["conversation"] == "onebot:GroupMessage:123"
    assert json.loads(row["key"])[0] == row["scope"]
    field = {
        "messages": "segments",
        "decisions": "decision_json",
        "topics": "interact",
        "diaries": "topics",
    }[category]
    assert isinstance(row[field], (list, dict))
    _, other = await invoke(
        dashboard.records, query={"category": category, "sessions": '["absent"]'}
    )
    assert other == {"items": [], "total": 0}


async def test_search_sort_pagination_and_stats(dashboard):
    _, result = await invoke(
        dashboard.records, query={"q": "天气", "sort": "seq", "order": "asc"}
    )
    assert result["total"] == 1 and result["items"][0]["seq"] == 1
    _, result = await invoke(
        dashboard.records, query={"sort": "seq", "order": "asc", "limit": 1, "page": 2}
    )
    assert result["items"][0]["seq"] == 2
    _, result = await invoke(dashboard.records, query={"q": "%' OR 1=1 --"})
    assert result["total"] == 0
    _, result = await invoke(dashboard.overview)
    assert result["stats"]["messages"] == 3 and result["stats"]["planned_replies"] == 1
    assert result["stats"]["topics"] == result["stats"]["diaries"] == 1


@pytest.mark.parametrize("category", ["messages", "decisions", "topics", "diaries"])
async def test_multiple_sessions_and_chat_type(dashboard, category):
    _, result = await invoke(
        dashboard.records,
        query={
            "category": category,
            "chat_type": "group",
            "sessions": json.dumps(
                ["onebot:GroupMessage:123", "onebot:FriendMessage:absent"]
            ),
        },
    )
    assert result["total"] > 0
    _, result = await invoke(
        dashboard.records, query={"category": category, "chat_type": "private"}
    )
    assert result["total"] == 0


async def test_group_and_private_can_be_selected_together(dashboard):
    message = dashboard.runtime.adapter.snapshot(
        Event("私聊记录", message_id="private")
    )
    await dashboard.runtime.storage.append(
        replace(
            message,
            scope=json.dumps(["onebot", "999", "private", "456"]),
            umo="onebot:FriendMessage:456",
            private=True,
            group_id="",
        )
    )
    selected = json.dumps(["onebot:GroupMessage:123", "onebot:FriendMessage:456"])
    _, result = await invoke(dashboard.records, query={"sessions": selected})
    assert result["total"] == 4
    _, result = await invoke(
        dashboard.records, query={"sessions": selected, "chat_type": "private"}
    )
    assert result["total"] == 1 and result["items"][0]["text"] == "私聊记录"


@pytest.mark.parametrize(
    "category,matching,excluded",
    [
        (
            "messages",
            {"kind": "in", "sender": "User", "component": "text"},
            {"kind": "out"},
        ),
        ("messages", {"sender": "42"}, {"component": "image"}),
        (
            "decisions",
            {"reply": "1", "emotion": "NEUTRAL", "required": "0", "trigger": "message"},
            {"reply": "0"},
        ),
        ("decisions", {"kind": "pending"}, {"emotion": "ANGER"}),
        (
            "topics",
            {"participant": "讨论天气", "bot_reply": "未见我参与"},
            {"participant": "absent"},
        ),
        ("diaries", {"kind": "0", "coverage_gap": "0"}, {"coverage_gap": "1"}),
    ],
)
async def test_category_specific_filters(dashboard, category, matching, excluded):
    _, result = await invoke(
        dashboard.records, query={"category": category, **matching}
    )
    assert result["total"] > 0
    _, result = await invoke(
        dashboard.records, query={"category": category, **excluded}
    )
    assert result["total"] == 0


async def test_session_choices_use_enabled_range_and_stats_accept_umo(dashboard):
    dashboard.runtime.settings.scope["manual_sessions"] = ["onebot:FriendMessage:456"]
    _, result = await invoke(
        dashboard.overview, query={"scope": "onebot:GroupMessage:123"}
    )
    assert result["stats"]["messages"] == 3
    assert {item["value"] for item in result["sessions"]} == {
        "onebot:GroupMessage:123",
        "onebot:FriendMessage:456",
    }
    dashboard.runtime.settings.scope["sessions"] = []
    _, result = await invoke(dashboard.overview)
    assert [item["value"] for item in result["sessions"]] == [
        "onebot:FriendMessage:456"
    ]


@pytest.mark.parametrize("session_id", ["123", "42_123"])
@pytest.mark.parametrize("user_alias", ["", "自定义群名"])
async def test_group_choices_keep_native_names(dashboard, session_id, user_alias):
    aliases = AsyncMock(
        return_value=[
            SimpleNamespace(
                umo=f"onebot:GroupMessage:{session_id}",
                creator_sender_id="42",
                user_alias=user_alias,
                auto_name="测试群名称",
            )
        ]
    )
    if session_id == "123":
        aliases.return_value.append(
            SimpleNamespace(
                umo="onebot:GroupMessage:99_123",
                creator_sender_id="99",
                user_alias="成员隔离会话别名",
                auto_name="测试群名称",
            )
        )
    dashboard.runtime.adapter.context.get_db = lambda: SimpleNamespace(
        get_umo_aliases=aliases
    )
    _, result = await invoke(dashboard.overview)
    assert result["sessions"][0]["title"] == (user_alias or "测试群名称")
    aliases.assert_awaited_once()
    aliases.return_value[0].auto_name = "更新后的群名"
    _, result = await invoke(dashboard.overview)
    assert result["sessions"][0]["title"] == (user_alias or "更新后的群名")


@pytest.mark.parametrize(
    "query",
    [
        {"category": "sessions"},
        {"sort": "timestamp;DELETE FROM messages"},
        {"limit": 101},
        {"page": 0},
        {"start": "invalid"},
        {"start": "2026-10-20", "end": "2026-10-01"},
        {"sessions": '"not-a-list"'},
        {"sessions": "[{}]"},
        {"sessions": "invalid-json"},
    ],
)
async def test_rejects_invalid_queries(dashboard, query):
    assert (await invoke(dashboard.records, query=query))[0] == 400


@pytest.mark.parametrize("category", ["messages", "decisions", "topics", "diaries"])
async def test_explicit_batch_deletion_and_diary_cascade(dashboard, category):
    _, result = await invoke(dashboard.records, query={"category": category})
    rows = result["items"]
    scope = rows[0]["scope"]
    before = await dashboard.runtime.storage.session(scope)
    status, result = await invoke(
        dashboard.delete, body={"category": category, "keys": [r["key"] for r in rows]}
    )
    assert status == 200 and result["deleted"] == len(rows)
    _, empty = await invoke(dashboard.records, query={"category": category})
    assert empty["total"] == 0
    after = await dashboard.runtime.storage.session(scope)
    assert before["last_seq"] == after["last_seq"] == 3
    if category == "diaries":
        _, topics = await invoke(dashboard.records, query={"category": "topics"})
        assert topics["total"] == 0
    if category == "messages":
        assert after["human_count"] == before["human_count"]
        assert len(await dashboard.runtime.storage.diaries(scope)) == 1


async def test_busy_scope_is_not_modified(dashboard):
    _, records = await invoke(dashboard.records)
    row = records["items"][0]
    async with dashboard.runtime.controller.lock(row["scope"]):
        status, _ = await invoke(
            dashboard.delete, body={"category": "messages", "keys": [row["key"]]}
        )
        assert status == 409
    _, records = await invoke(dashboard.records)
    assert records["total"] == 3


@pytest.mark.parametrize(
    "endpoint",
    [
        "overview",
        "records",
        "delete",
        "settings",
        "save_settings",
        "reset_all",
        "prompt_diff",
    ],
)
async def test_endpoints_require_dashboard_identity(dashboard, endpoint):
    assert (await invoke(getattr(dashboard, endpoint), username=None))[0] == 403


async def test_config_validation_revision_and_native_reload(dashboard):
    _, settings = await invoke(dashboard.settings)
    edited = copy.deepcopy(settings["config"])
    edited["recorder"]["retention"] = 0
    status, _ = await invoke(
        dashboard.save_settings,
        body={"config": edited, "revision": settings["revision"]},
    )
    assert status == 400 and dashboard.plugin.config["recorder"]["retention"] > 0
    edited["recorder"]["retention"] = 600
    status, _ = await invoke(
        dashboard.save_settings, body={"config": edited, "revision": "stale"}
    )
    assert status == 409
    status, result = await invoke(
        dashboard.save_settings,
        body={"config": edited, "revision": settings["revision"]},
    )
    assert status == 200 and result["reloaded"]
    dashboard.plugin.context._star_manager.reload.assert_awaited_once_with(
        Dashboard.plugin_name
    )
    assert dashboard.plugin.config["recorder"]["retention"] == 600
    saved = json.loads(
        Path(dashboard.plugin.config.config_path).read_text(encoding="utf-8-sig")
    )
    assert saved["recorder"]["retention"] == 600


async def test_registration_cleanup_preserves_other_plugins(dashboard):
    dashboard.register()
    apis = dashboard.plugin.context.registered_web_apis
    assert len(apis) == 7
    other = ("/other/ping", object(), ["GET"], "ping")
    apis.append(other)
    dashboard.close()
    assert apis == [other]


@pytest.mark.parametrize("confirmation", [None, "", "incorrect"])
async def test_reset_all_requires_exact_confirmation(dashboard, confirmation):
    dashboard.runtime.reset_all = AsyncMock()
    status, _ = await invoke(dashboard.reset_all, body={"confirmation": confirmation})
    assert status == 400
    dashboard.runtime.reset_all.assert_not_awaited()


async def test_reset_all_runs_without_config_save_or_plugin_reload(dashboard):
    dashboard.runtime.context.conversation_manager = SimpleNamespace(
        get_conversations=AsyncMock(return_value=[]),
        get_curr_conversation_id=AsyncMock(return_value="old"),
        get_conversation=AsyncMock(return_value=SimpleNamespace(persona_id="persona")),
        new_conversation=AsyncMock(return_value="new"),
    )
    before = dashboard.plugin.config.config_path
    saved = Path(before).read_bytes()
    status, result = await invoke(
        dashboard.reset_all,
        body={
            "confirmation": dashboard.runtime.admin.all_confirmation,
        },
    )
    assert status == 200 and result == {"reset": True, "conversations": 1}
    for category in ("messages", "decisions", "topics", "diaries"):
        _, result = await invoke(dashboard.records, query={"category": category})
        assert result["total"] == 0
    dashboard.runtime.context.conversation_manager.new_conversation.assert_awaited_once_with(
        "onebot:GroupMessage:123", platform_id="onebot", persona_id="persona"
    )
    assert Path(before).read_bytes() == saved
    dashboard.plugin.context._star_manager.reload.assert_not_awaited()


async def test_reset_all_reports_partial_failure(dashboard):
    dashboard.runtime.reset_all = AsyncMock(side_effect=OSError("internal path"))
    status, result = await invoke(
        dashboard.reset_all,
        body={
            "confirmation": dashboard.runtime.admin.all_confirmation,
        },
    )
    assert status == 500 and "部分会话可能已重置" in result["message"]
    assert "internal path" not in result["message"]


async def test_onebot_group_names_are_batched_and_cached(dashboard):
    client = SimpleNamespace(
        call_action=AsyncMock(
            return_value=[{"group_id": 123, "group_name": "真正的群名"}]
        )
    )
    platform = SimpleNamespace(
        meta=lambda: SimpleNamespace(name="aiocqhttp"), get_client=lambda: client
    )
    dashboard.runtime.adapter.context.get_platform_inst = lambda platform_id: platform
    dashboard.runtime.adapter.context.get_db = lambda: SimpleNamespace(
        get_umo_aliases=AsyncMock(
            return_value=[
                SimpleNamespace(
                    umo="onebot:GroupMessage:123",
                    user_alias="",
                    auto_name=None,
                    creator_sender_id="42",
                )
            ]
        )
    )
    for _ in range(2):
        _, result = await invoke(dashboard.overview)
        assert result["sessions"][0]["title"] == "真正的群名"
    client.call_action.assert_awaited_once_with("get_group_list")


async def test_group_name_failure_retains_cache_and_respects_alias(dashboard):
    client = SimpleNamespace(call_action=AsyncMock(side_effect=RuntimeError("offline")))
    platform = SimpleNamespace(
        meta=lambda: SimpleNamespace(name="aiocqhttp"), get_client=lambda: client
    )
    adapter = dashboard.runtime.adapter
    adapter.context.get_platform_inst = lambda platform_id: platform
    adapter.group_names["onebot"] = (0, {"123": "缓存群名"})
    for _ in range(2):
        _, result = await invoke(dashboard.overview)
        assert result["sessions"][0]["title"] == "缓存群名"
    client.call_action.assert_awaited_once()
    adapter.context.get_db = lambda: SimpleNamespace(
        get_umo_aliases=AsyncMock(
            return_value=[
                SimpleNamespace(
                    umo="onebot:GroupMessage:123",
                    user_alias="我的群备注",
                    auto_name="旧群名",
                    creator_sender_id="42",
                )
            ]
        )
    )
    _, result = await invoke(dashboard.overview)
    assert result["sessions"][0]["title"] == "我的群备注"
    client.call_action.assert_awaited_once()


@pytest.mark.parametrize("name", ["behavior", "expression", "group", "private"])
async def test_default_prompts_are_runtime_fallbacks_not_config_values(dashboard, name):
    prompts = dashboard.runtime.prompts
    assert prompts.settings.prompts[name] == ""
    assert await prompts.fragment(name) == prompts.text[name].strip()
    assert prompts.settings.prompts[name] == ""
    prompts.settings.prompts[name] = "我的自定义提示词"
    assert await prompts.fragment(name) == "我的自定义提示词"
    prompts.settings.prompts[name + "_persona"] = "chosen"
    prompts.persona_manager.get_persona.return_value = SimpleNamespace(
        system_prompt="人格正文"
    )
    assert await prompts.fragment(name) == "人格正文"
    prompts.persona_manager.get_persona.return_value = SimpleNamespace(
        system_prompt="  "
    )
    assert await prompts.fragment(name) == prompts.text[name].strip()


async def test_prompt_diff_reads_default_without_saving(dashboard):
    before = Path(dashboard.plugin.config.config_path).read_bytes()
    status, result = await invoke(
        dashboard.prompt_diff, body={"name": "behavior", "text": "自定义规划\n新的一行"}
    )
    assert status == 200
    assert "--- 默认提示词" in result["lines"]
    assert "+自定义规划" in result["lines"]
    assert any(
        line.startswith("-") and not line.startswith("---") for line in result["lines"]
    )
    _, result = await invoke(
        dashboard.prompt_diff, body={"name": "behavior", "text": "  "}
    )
    assert result["lines"] == []
    status, _ = await invoke(
        dashboard.prompt_diff, body={"name": "../../main", "text": "bad"}
    )
    assert status == 400
    assert Path(dashboard.plugin.config.config_path).read_bytes() == before
