"""Exercise view endpoints through the host request context and real SQLite."""

import copy
import json
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
        dashboard.records, query={"category": category, "scope": "absent"}
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


@pytest.mark.parametrize(
    "query",
    [
        {"category": "sessions"},
        {"sort": "timestamp;DELETE FROM messages"},
        {"limit": 101},
        {"page": 0},
        {"start": "invalid"},
        {"start": "2026-10-20", "end": "2026-10-01"},
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
    "endpoint", ["overview", "records", "delete", "settings", "save_settings"]
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
    assert len(apis) == 5
    other = ("/other/ping", object(), ["GET"], "ping")
    apis.append(other)
    dashboard.close()
    assert apis == [other]
