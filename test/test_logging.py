"""Log routing, retention, credential masking and independent trace contexts."""

import asyncio
import json
import logging
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from humanization_test.utils.plugin_log import PluginLog


def entries(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def test_runtime_rolls_exactly_1000_lines_across_reload(tmp_path):
    console = Mock()
    directory = tmp_path / "log"
    log = PluginLog(directory, False, console, ZoneInfo("Asia/Shanghai"))
    await log.open()
    for index in range(1025):
        log.info("test.core", index=index)
    log.debug("test.private", text="never written")
    await log.close()
    rows = entries(directory / "runtime.log")
    assert len(rows) == 1000
    assert rows[0]["data"]["index"] == 25
    assert console.log.call_count == 1025
    assert (directory / "dev.log").read_bytes() == b""
    assert b"never written" not in (directory / "runtime.log").read_bytes()
    assert b"\n" not in (directory / "runtime.log").read_bytes().replace(b"\r\n", b"")
    next_log = PluginLog(directory, False, console, ZoneInfo("Asia/Shanghai"))
    await next_log.open()
    next_log.info("test.reloaded")
    await next_log.close()
    rows = entries(directory / "runtime.log")
    assert len(rows) == 1000 and rows[0]["data"]["index"] == 26
    assert rows[-1]["event"] == "test.reloaded"


async def test_debug_appends_all_records_without_console_or_runtime_changes(tmp_path):
    console = Mock()
    directory = tmp_path / "log"
    ordinary = PluginLog(directory, False, console, ZoneInfo("Asia/Shanghai"))
    await ordinary.open()
    ordinary.info("test.normal")
    await ordinary.close()
    runtime = (directory / "runtime.log").read_bytes()
    console.reset_mock()
    for _ in range(2):
        log = PluginLog(directory, True, console, ZoneInfo("Asia/Shanghai"))
        await log.open()
        for index in range(600):
            log.debug("test.detail", text="first\nsecond", index=index)
        log.info("test.core")
        await log.close()
    rows = entries(directory / "dev.log")
    assert len(rows) == 1202
    assert rows[0]["data"]["text"] == "first\nsecond"
    assert console.mock_calls == []
    assert (directory / "runtime.log").read_bytes() == runtime


async def test_credentials_binary_and_exception_detail_are_masked(tmp_path):
    console = Mock()
    log = PluginLog(tmp_path / "log", True, console, ZoneInfo("Asia/Shanghai"))
    await log.open()
    log.debug(
        "tool.result",
        arguments={
            "api_key": "secretkey",
            "headers": {"Authorization": "Bearer secretvalue"},
        },
        result="token=secrettoken and sk-abcdefghijklmnop",
        image_base64="SGVsbG8=",
        binary=b"private",
        embedded="data:image/png;base64,SGVsbG8=",
    )
    try:
        raise ValueError("password=secretpassword")
    except ValueError:
        log.exception("test.failed")
    await log.close()
    raw = (tmp_path / "log" / "dev.log").read_text(encoding="utf-8")
    for secret in (
        "secretkey",
        "secretvalue",
        "secrettoken",
        "sk-abcdefghijklmnop",
        "secretpassword",
        "SGVsbG8=",
        "private",
    ):
        assert secret not in raw
    rows = entries(tmp_path / "log" / "dev.log")
    assert rows[-1]["data"]["error_type"] == "ValueError"
    assert "Traceback" in rows[-1]["data"]["exception"]
    assert not console.mock_calls


async def test_normal_exception_contains_no_original_error_message(tmp_path):
    console = Mock()
    log = PluginLog(tmp_path / "log", False, console, ZoneInfo("Asia/Shanghai"))
    await log.open()
    try:
        raise ValueError("private user content and credentials")
    except ValueError:
        log.exception("test.failed", run=3)
    await log.close()
    row = entries(tmp_path / "log" / "runtime.log")[0]
    assert row["data"] == {"run": 3, "error_type": "ValueError"}
    assert console.log.call_args.args[0] == logging.ERROR
    assert "private user content" not in str(console.mock_calls)


async def test_trace_context_isolated_between_concurrent_tasks(tmp_path):
    log = PluginLog(tmp_path / "log", True, Mock(), ZoneInfo("Asia/Shanghai"))
    await log.open()

    async def work(name):
        async with log.context(name):
            log.debug("test.start")
            await asyncio.sleep(0)
            log.debug("test.end")

    await asyncio.gather(work("reply"), work("summary"))
    assert not log.trace.get()
    await log.close()
    rows = entries(tmp_path / "log" / "dev.log")
    traces = {row["trace"] for row in rows}
    assert len(traces) == 2
    assert all(sum(row["trace"] == trace for row in rows) == 2 for trace in traces)


async def test_writer_io_failure_reports_once_and_does_not_block_shutdown(
    tmp_path, monkeypatch
):
    console = Mock()
    log = PluginLog(tmp_path / "log", True, console, ZoneInfo("Asia/Shanghai"))
    await log.open()

    def fail(lines):
        raise OSError("private path")

    monkeypatch.setattr(log, "_write_batch", fail)
    log.info("test.one")
    await log.flush()
    log.info("test.two")
    await log.close()
    console.error.assert_called_once()
    assert "private path" not in str(console.mock_calls)


@pytest.mark.parametrize("debug", [False, True])
async def test_project_log_routing_and_private_text(
    tmp_path, config, monkeypatch, debug
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from humanization_test.core.runtime import Runtime
    from test_host_contract import Event, consume, replay

    from astrbot.core.provider.entities import LLMResponse, ProviderRequest
    from astrbot.core.star.session_llm_manager import SessionServiceManager

    config["logging"]["debug"] = debug
    config["scope"]["sessions"] = ["onebot:GroupMessage:123"]
    config["controller"]["debounce_seconds"] = 0
    console = Mock()
    context = SimpleNamespace(
        persona_manager=SimpleNamespace(get_persona=AsyncMock()),
        get_config=lambda **kw: {
            "provider_settings": {"enable": True},
            "agent_runner": {"runner_type": "local"},
        },
        get_current_chat_provider_id=AsyncMock(return_value="main"),
        llm_generate=AsyncMock(
            return_value=LLMResponse(
                role="assistant", completion_text="auxiliary result"
            )
        ),
    )
    monkeypatch.setattr(
        SessionServiceManager,
        "should_process_llm_request",
        AsyncMock(return_value=True),
    )
    runtime = Runtime(context, config, tmp_path, console)
    await runtime.initialize()
    event = Event("private input", direct=True)
    runtime.adapter.request = AsyncMock(
        return_value=ProviderRequest(prompt="private input")
    )
    await consume(runtime.observe(event))
    generator = runtime.participate(event)
    request = await anext(generator)
    await runtime.inject(event, request)
    await runtime.adapter.generate("auxiliary", "private system", "api_key=privatekey")
    await runtime.validate(
        event,
        LLMResponse(role="assistant", completion_text="private reply$second reply"),
    )
    await replay(runtime, event, generator)
    await runtime.terminate()
    path = tmp_path / "log" / ("dev.log" if debug else "runtime.log")
    raw = path.read_text(encoding="utf-8")
    rows = entries(path)
    assert rows[-1]["event"] == "runtime.stop"
    if debug:
        assert not console.mock_calls
        assert "private input" in raw and "private reply" in raw
        assert "privatekey" not in raw
        assert any(row["event"] == "model.response" for row in rows)
        assert (tmp_path / "log" / "runtime.log").read_bytes() == b""
    else:
        assert console.log.called
        assert "private input" not in raw and "private reply" not in raw
        assert "private system" not in raw and "privatekey" not in raw
        assert (tmp_path / "log" / "dev.log").read_bytes() == b""


async def test_tool_hooks_record_results_without_credentials_or_image_bodies(tmp_path):
    from types import SimpleNamespace

    from humanization_test.main import Humanization
    from mcp.types import CallToolResult, ImageContent, TextContent
    from test_host_contract import Event

    log = PluginLog(tmp_path / "log", True, Mock(), ZoneInfo("Asia/Shanghai"))
    await log.open()
    instance = Humanization.__new__(Humanization)
    instance.runtime = SimpleNamespace(log=log)
    event = Event()
    event.set_extra("humanization_turn", {"run": 4})
    tool = SimpleNamespace(name="test_tool")
    arguments = {"api_key": "toolsecret", "query": "test query"}
    result = CallToolResult(
        content=[
            TextContent(type="text", text="tool text result"),
            ImageContent(type="image", mimeType="image/png", data="aW1hZ2U="),
        ],
        structuredContent={"password": "structuredsecret", "count": 2},
        isError=False,
    )
    await instance.tool_started(event, tool, arguments)
    await instance.tool_finished(event, tool, arguments, result)
    await log.close()
    raw = (tmp_path / "log" / "dev.log").read_text(encoding="utf-8")
    assert "tool text result" in raw and "test query" in raw
    assert (
        "toolsecret" not in raw
        and "structuredsecret" not in raw
        and "aW1hZ2U=" not in raw
    )
    rows = entries(tmp_path / "log" / "dev.log")
    assert [row["event"] for row in rows] == ["tool.start", "tool.complete"]
    assert rows[-1]["data"]["structured_result"]["count"] == 2
