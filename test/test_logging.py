"""Logging contracts: native formatting, isolation, recovery and reversible tracing."""

import asyncio
import json
import logging
import queue
import re
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from humanization_test.utils.log_tracking import CallTracker
from humanization_test.utils.plugin_log import PluginLog


def entries(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.search(
            r"\[(TRACK|DBUG|INFO|WARN|ERRO|CRIT)\].*?: (.*?) \(([\w.]+)\)(.*)", line
        )
        if match:
            data = {}
            for key, value in re.findall(r"(\w+)=([^\s]+)", match[4]):
                try:
                    data[key] = json.loads("null" if value == "none" else value)
                except ValueError:
                    data[key] = value
            rows.append(
                {
                    "event": match[3],
                    "level": match[1],
                    "body": match[4],
                    "line": line,
                    "data": data,
                }
            )
    return rows


def make_log(tmp_path, **options):
    return PluginLog(
        tmp_path / "log",
        options.pop("debug", False),
        Mock(),
        ZoneInfo("Asia/Shanghai"),
        **options,
    )


@pytest.mark.parametrize(
    "level,count",
    [
        ("TRACK", 6),
        ("DEBUG", 5),
        ("INFO", 4),
        ("WARNING", 3),
        ("ERROR", 2),
        ("CRITICAL", 1),
    ],
)
async def test_level_filter_and_native_format(tmp_path, level, count):
    log = make_log(tmp_path, level=level, debug=True)
    await log.open()
    for severity in ("TRACK", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        if severity == "TRACK":
            log.track("test.level", (__file__, 1, "test_level"), severity=severity)
        else:
            getattr(log, severity.lower())("test.level", severity=severity)
    await log.close()
    rows = entries(log.directory / "humanization.log")
    assert len(rows) == count
    assert "[astrbot_plugin_humanization]" in rows[0]["line"]
    assert "test.test_logging:" in rows[0]["line"] or "python.py:" in rows[0]["line"]
    assert not log.console.mock_calls
    assert {p.name for p in log.directory.iterdir()} == {"humanization.log"}
    content = (log.directory / "humanization.log").read_bytes()
    assert b"\r\n" in content and b"\n" not in content.replace(b"\r\n", b"")


async def test_echo_mask_and_credentials_share_sanitized_record(tmp_path):
    log = make_log(tmp_path, level="DEBUG", mask=True, echo=True)
    await log.open()
    log.info(
        "test.message",
        conversation="Bot:GroupMessage:753093968",
        sender_name="测试用户",
        text="这是保密的聊天正文",
        sender_id=123456789,
        token="very-secret",
        note="api_key=hidden-secret",
    )
    await log.close()
    raw = (log.directory / "humanization.log").read_text(encoding="utf-8")
    assert "Bot:GroupMessage:75******8" in raw
    assert "测**户" in raw and "12******9" in raw
    for secret in (
        "753093968",
        "测试用户",
        "这是保密的聊天正文",
        "very-secret",
        "hidden-secret",
    ):
        assert secret not in raw
    forwarded = log.console.handle.call_args.args[0]
    assert forwarded.pathname.endswith("test_logging.py")
    assert forwarded.getMessage() in raw
    assert "test.message" in forwarded.getMessage()


@pytest.mark.parametrize(
    "text,expected",
    [("甲", "甲"), ("甲乙", "甲**"), ("甲乙丙", "甲*丙"), ("甲乙丙丁", "甲**丁")],
)
def test_short_mask_rules(text, expected):
    assert PluginLog.mask_text(text) == expected


async def test_exception_at_info_is_synchronous_and_keeps_stack(tmp_path):
    log = make_log(tmp_path)
    await log.open()
    log.info("test.start")
    try:
        raise ValueError("request failed api_key=privatekey")
    except ValueError:
        log.exception("test.failed")
    raw = (log.directory / "humanization.log").read_text(encoding="utf-8")
    assert raw.index("test.start") < raw.index("test.failed")
    assert "test_logging.py:" in raw and "ValueError" in raw
    assert "request failed" in raw and "privatekey" not in raw
    await log.close()


async def test_rotation_reload_clear_and_old_files_untouched(tmp_path):
    log = make_log(tmp_path, max_mb=0.001)
    log.directory.mkdir()
    old = log.directory / "dev.log"
    old.write_text("old log", encoding="utf-8")
    await log.open()
    for index in range(120):
        log.info("test.record", index=index)
    await log.close()
    assert (log.directory / "humanization.log.3").exists()
    assert not (log.directory / "humanization.log.4").exists()
    assert old.read_text(encoding="utf-8") == "old log"
    fresh = make_log(tmp_path)
    await fresh.open()
    fresh.info("test.pending")
    await fresh.clear()
    fresh.info("test.after")
    await fresh.close()
    assert [r["event"] for r in entries(fresh.directory / "humanization.log")] == [
        "test.after"
    ]


async def test_dead_worker_flush_queue_pressure_and_write_failure(
    tmp_path, monkeypatch, capsys
):
    log = make_log(tmp_path, level="DEBUG")
    await log.open()
    # Stop the consumer so a deterministic full queue can be exercised.
    log.queue.put(None)
    await asyncio.to_thread(log.worker.join)

    class Alive:
        def is_alive(self):
            return True

    log.worker = Alive()
    log.queue = queue.Queue(maxsize=1)
    log.debug("test.first")
    log.debug("test.dropped")
    assert log.dropped == 1
    log.info("test.important")
    log.worker = None
    await asyncio.wait_for(log.flush(), 2)
    assert "test.important" in (log.directory / "humanization.log").read_text(
        encoding="utf-8"
    )

    def fail(record):
        raise OSError("disk unavailable")

    monkeypatch.setattr(log.handler, "handle", fail)
    log.error("test.failure")
    log.error("test.failure.again")
    assert capsys.readouterr().err.count("log writer unavailable") == 1
    await log.close()


async def test_context_correlation_and_usage_join(tmp_path):
    log = make_log(tmp_path)
    await log.open()

    async def operation(name):
        async with log.context(name):
            log.info("gate.start")
            await asyncio.sleep(0)
            log.model_usage(
                purpose="controller", usage={"input": 100, "input_cached": 60}
            )
            log.info("gate.complete")

    await asyncio.gather(operation("first"), operation("second"))
    await log.close()
    rows = entries(log.directory / "humanization.log")
    assert len(rows) == 4
    ids = [re.search(r"\[id=([^\]]+)\]", row["line"])[1] for row in rows]
    assert len(set(ids)) == 2 and all(ids.count(value) == 2 for value in set(ids))
    assert "tokens_input=100" in str(rows) and not log.trace.get()


async def test_track_preserves_async_generator_send_throw_and_cancellation(tmp_path):
    log = make_log(tmp_path, level="TRACK", debug=True, echo=True)
    await log.open()
    tracker = CallTracker(log)

    async def stream():
        try:
            value = yield "first"
            yield value
        except ValueError:
            yield "caught"

    tracked = tracker._wrap(stream)
    generator = tracked()
    assert await anext(generator) == "first"
    assert await generator.asend("second") == "second"
    assert await generator.athrow(ValueError("test")) == "caught"
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    async def wait():
        await asyncio.Event().wait()

    task = asyncio.create_task(tracker._wrap(wait)())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await log.close()
    raw = (log.directory / "humanization.log").read_text(encoding="utf-8")
    assert "track.return" in raw and "CancelledError" in raw
    forwarded = log.console.handle.call_args.args[0]
    assert forwarded.levelno == logging.DEBUG and forwarded.msg.startswith("[TRACK]")


async def test_track_install_restore_and_no_host_patching(tmp_path):
    from humanization_test.core.controller.protocol import ControllerProtocol
    from humanization_test.core.settings import Settings

    log = make_log(tmp_path, level="TRACK", debug=True)
    await log.open()
    tracker = CallTracker(log)
    original = Settings.scope_action
    parse = ControllerProtocol.parse
    host_sleep = asyncio.sleep
    try:
        tracker.install("humanization_test")
        assert Settings.scope_action is not original
        assert asyncio.sleep is host_sleep
        assert ControllerProtocol.parse.__wrapped__ is parse.__func__
    finally:
        tracker.close()
    assert Settings.scope_action is original
    await log.close()


async def test_startup_configuration_failure_is_recorded_before_open(config, tmp_path):
    from humanization_test.core.runtime import Runtime

    config["controller"]["robot_name"] = ""
    with pytest.raises(ValueError):
        Runtime(SimpleNamespace(), config, tmp_path, Mock())
    raw = (tmp_path / "log" / "humanization.log").read_text(encoding="utf-8")
    assert "CRIT" in raw and "runtime.initialize.failed" in raw and "ValueError" in raw


async def test_track_runtime_lifecycle_restores_all_wrappers(config, tmp_path):
    from unittest.mock import AsyncMock

    from humanization_test.core.astrbot_adapter import AstrBotAdapter
    from humanization_test.core.runtime import Runtime

    config["logging"].update(debug=True, level="TRACK")
    original = AstrBotAdapter.generate
    context = SimpleNamespace(persona_manager=SimpleNamespace(get_persona=AsyncMock()))
    runtime = Runtime(context, config, tmp_path, Mock())
    try:
        assert AstrBotAdapter.generate is not original
        assert runtime.controller.generate.__func__ is AstrBotAdapter.generate
        await runtime.initialize()
        # Real database transaction/context-manager paths execute under TRACK.
        await runtime.storage.reset_targets()
    finally:
        await runtime.terminate()
    assert AstrBotAdapter.generate is original
    assert not runtime.log.worker
    raw = (runtime.log.directory / "humanization.log").read_text(encoding="utf-8")
    assert "Storage.reset_targets" in raw and "track.return" in raw
    assert "runtime.stop" in raw


def test_track_requires_debug_and_invalid_level_is_rejected(config):
    from humanization_test.core.settings import Settings

    config["logging"]["level"] = "TRACK"
    assert Settings(config).logging["level"] == "INFO"
    config["logging"]["level"] = "INVALID"
    with pytest.raises(ValueError, match="log level"):
        Settings(config)


async def test_normal_producer_does_not_wait_for_slow_disk(tmp_path, monkeypatch):
    log = make_log(tmp_path)
    await log.open()
    entered, release = threading.Event(), threading.Event()
    original = log.handler.handle

    def slow(record):
        entered.set()
        release.wait(3)
        original(record)

    monkeypatch.setattr(log.handler, "handle", slow)
    log.info("test.first")
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.wait_for(asyncio.to_thread(log.info, "test.second"), 1)
    finally:
        release.set()
        await log.close()
    assert len(entries(log.directory / "humanization.log")) == 2


async def test_cancelled_close_still_joins_writer(tmp_path, monkeypatch):
    log = make_log(tmp_path)
    await log.open()
    entered, release = threading.Event(), threading.Event()
    original = log._drain

    def slow_drain():
        entered.set()
        release.wait(3)
        original()

    monkeypatch.setattr(log, "_drain", slow_drain)
    task = asyncio.create_task(log.close())
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert log.closed and log.worker is None and log.handler is None


async def test_unknown_token_count_remains_missing_not_redacted(tmp_path):
    log = make_log(tmp_path)
    await log.open()
    log.model_usage(
        purpose="main", usage={"input": 10, "input_cached": None}, api_key=12345
    )
    await log.close()
    raw = (log.directory / "humanization.log").read_text(encoding="utf-8")
    assert "tokens_input_cached=none" in raw and "12345" not in raw


async def test_track_real_registered_event_and_command_chain(
    config, tmp_path, monkeypatch
):
    import json
    from pathlib import Path
    from unittest.mock import AsyncMock

    from humanization_test.main import Humanization
    from test_host_contract import Event, consume

    from astrbot.api import AstrBotConfig
    from astrbot.api.star import StarTools
    from astrbot.core.star.star_handler import star_handlers_registry

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "_conf_schema.json").read_text(
            encoding="utf-8"
        )
    )
    native_config = AstrBotConfig(str(tmp_path / "config.json"), schema=schema)
    native_config["logging"].update(debug=True, level="TRACK")
    monkeypatch.setattr(StarTools, "get_data_dir", lambda: tmp_path)
    context = SimpleNamespace(persona_manager=SimpleNamespace(get_persona=AsyncMock()))
    original = next(
        h
        for h in star_handlers_registry
        if h.handler.__module__ == Humanization.__module__
        and h.handler_name == "observe"
    ).handler
    instance = Humanization(context, native_config)
    try:
        await instance.runtime.initialize()
        handler = next(
            h
            for h in star_handlers_registry
            if h.handler.__module__ == Humanization.__module__
            and h.handler_name == "observe"
        )
        assert handler.handler is not original
        await consume(handler.handler(instance, Event("/status")))
    finally:
        await instance.terminate()
    assert handler.handler is original
    raw = (instance.runtime.log.directory / "humanization.log").read_text(
        encoding="utf-8"
    )
    assert "Humanization.observe" in raw and "Runtime.observe" in raw


async def test_binary_and_nested_credentials_are_never_written(tmp_path):
    log = make_log(tmp_path, level="DEBUG")
    await log.open()
    log.debug(
        "test.payload",
        result={
            "image_data": "PRIVATE_BINARY_BODY",
            "authorization": "secret-credential",
            "message": "Bearer secret-bearer",
            "nested": {"api_key": "secret-nested"},
        },
    )
    await log.close()
    raw = (log.directory / "humanization.log").read_text(encoding="utf-8")
    for value in (
        "PRIVATE_BINARY_BODY",
        "secret-credential",
        "secret-bearer",
        "secret-nested",
    ):
        assert value not in raw
    assert "binary(length=" in raw
