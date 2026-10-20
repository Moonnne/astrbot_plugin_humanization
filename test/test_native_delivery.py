"""Replay through real host decoration, responding and completion hooks."""

import asyncio
import copy
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_host_contract import Event, consume
from test_host_contract import plugin as plugin

from astrbot.api.event import MessageChain
from astrbot.api.message_components import At, File, Image, Json, Plain, Record, Reply
from astrbot.core.astr_agent_run_util import run_agent
from astrbot.core.config.default import DEFAULT_CONFIG
from astrbot.core.message.message_event_result import ResultContentType
from astrbot.core.pipeline.context_utils import call_handler
from astrbot.core.pipeline.process_stage.stage import ProcessStage, StarRequestSubStage
from astrbot.core.pipeline.respond.stage import RespondStage
from astrbot.core.pipeline.result_decorate import stage as decorate_module
from astrbot.core.pipeline.result_decorate.stage import ResultDecorateStage
from astrbot.core.provider.entities import LLMResponse, ProviderRequest
from astrbot.core.star.session_llm_manager import SessionServiceManager
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType, star_handlers_registry


@pytest.fixture
async def native(plugin, monkeypatch):
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["platform_settings"].update(
        reply_prefix="", reply_with_quote=False, reply_with_mention=False
    )
    config["platform_settings"]["segmented_reply"]["enable"] = False
    config["provider_tts_settings"]["enable"] = False
    config["content_safety"]["also_use_in_response"] = False
    config["t2i"] = False
    config["provider_settings"]["display_reasoning_text"] = False
    plugin.context.get_config = lambda **kw: config
    plugin.context.get_using_tts_provider_async = AsyncMock(return_value=None)
    hooks = []

    async def after(event):
        hooks.append(list(event.get_result().chain))

    def metadata(name, handler):
        return SimpleNamespace(
            handler_module_path="humanization.native.test",
            handler_name=name,
            handler_full_name=f"humanization.native.test.{name}",
            event_type=EventType.OnAfterMessageSentEvent
            if name in {"record", "observer"}
            else EventType.OnDecoratingResultEvent,
            extras_configs={},
            event_filters=[],
            handler=handler,
        )

    extra_decorators = []
    callbacks = {
        EventType.OnDecoratingResultEvent: [metadata("defer", plugin.defer_result)],
        EventType.OnAfterMessageSentEvent: [
            metadata("record", plugin.after_sent),
            metadata("observer", after),
        ],
    }
    monkeypatch.setitem(
        star_map,
        "humanization.native.test",
        SimpleNamespace(name="Humanization", display_name="Humanization"),
    )
    monkeypatch.setattr(
        star_handlers_registry,
        "get_handlers_by_event_type",
        lambda kind, **kw: (
            callbacks.get(kind, [])
            + (extra_decorators if kind == EventType.OnDecoratingResultEvent else [])
        ),
    )
    process = ProcessStage()
    ctx = SimpleNamespace(
        astrbot_config=config, plugin_manager=SimpleNamespace(context=plugin.context)
    )
    process.ctx = ctx

    plugin.adapter.request = AsyncMock(return_value=ProviderRequest(prompt="你好"))

    async def run(event, agent):
        event.set_extra("activated_handlers", [SimpleNamespace(event_filters=[])])
        internal = bool(
            event.get_extra("humanization_scheduled")
            or event.get_extra("humanization_idle")
        )
        if not internal:
            await consume(plugin.observe(event))

        async def handler(event):
            async for result in call_handler(
                event, plugin.observe if internal else plugin.participate
            ):
                yield result

        process.star_request_sub_stage = SimpleNamespace(process=handler)
        process.agent_sub_stage = SimpleNamespace(process=agent)
        decorate = ResultDecorateStage()
        respond = RespondStage()
        await decorate.initialize(ctx)
        await respond.initialize(ctx)
        async for _ in process.process(event):
            await consume(decorate.process(event))
            await respond.process(event)

    async def answer(event, text="没有。$你继续", media=None, saved=None):
        response = LLMResponse(
            role="assistant", completion_text=text, result_chain=media
        )
        await plugin.validate(event, response)
        chain = media if media else MessageChain().message(text)
        event.set_result(
            event.chain_result(chain.chain).set_result_content_type(
                ResultContentType.LLM_RESULT
            )
        )
        yield
        if saved is not None:
            saved.append("history saved")

    return SimpleNamespace(
        config=config,
        run=run,
        answer=answer,
        hooks=hooks,
        decorators=extra_decorators,
        metadata=metadata,
    )


async def test_agent_finishes_before_replay_and_native_quote_prefix_hooks_survive(
    plugin, native
):
    native.config["platform_settings"].update(
        reply_prefix="前缀：", reply_with_quote=True, reply_with_mention=True
    )
    saved = []
    event = Event(direct=True)
    original_send = event.send

    async def send(chain):
        assert saved == ["history saved"]
        await original_send(chain)

    event.send = send

    async def agent(event):
        async for result in native.answer(event, saved=saved):
            yield result

    await native.run(event, agent)
    assert len(event.sent) == len(native.hooks) == 2
    assert all(
        isinstance(chain.chain[0], Reply) and isinstance(chain.chain[1], At)
        for chain in event.sent
    )
    assert [chain.get_plain_text().strip() for chain in event.sent] == [
        "前缀：没有",
        "前缀：你继续",
    ]
    assert event.get_extra("humanization_turn") is None
    assert event.get_extra("enable_streaming") is None
    assert (await plugin.storage.rows("SELECT * FROM reply_runs"))[0][
        "status"
    ] == "processed"


async def test_trailing_emoji_survives_native_replay_without_format_repair(
    plugin, native
):
    plugin.adapter.generate = AsyncMock()
    event = Event(direct=True)

    async def agent(event):
        async for result in native.answer(event, text="没有。$你继续😑"):
            yield result

    await native.run(event, agent)
    assert [chain.get_plain_text() for chain in event.sent] == ["没有", "你继续😑"]
    assert len(native.hooks) == 2
    plugin.adapter.generate.assert_not_awaited()
    assert event.get_extra("humanization_turn") is None


@pytest.mark.parametrize("mode", ["quote", "tts", "t2i", "segments", "tool_notice"])
async def test_scheduled_event_keeps_native_decorators_and_completion_hooks(
    plugin, native, monkeypatch, mode
):
    from test_scheduling import Clock

    plugin.settings.controller.update(mode="scheduled", group=1, force_at=True)
    queue = asyncio.Queue()
    plugin.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    plugin.scheduler.clock = clock
    plugin.scheduler.call_later = clock.later
    native.config["platform_settings"]["reply_with_quote"] = mode == "quote"
    if mode == "tts":
        native.config["provider_tts_settings"].update(
            enable=True,
            dual_output=False,
            use_file_service=False,
            trigger_probability=1,
        )
        plugin.context.get_using_tts_provider_async = AsyncMock(
            return_value=SimpleNamespace(get_audio=AsyncMock(return_value="voice.wav"))
        )
        monkeypatch.setattr(
            SessionServiceManager,
            "should_process_tts_request",
            AsyncMock(return_value=True),
        )
    if mode == "t2i":
        native.config.update(t2i=True, t2i_word_threshold=1)
        monkeypatch.setattr(
            decorate_module.html_renderer,
            "render_t2i",
            AsyncMock(return_value="image.png"),
        )
    if mode == "segments":
        native.config["platform_settings"]["segmented_reply"].update(
            enable=True,
            interval="0,0",
            interval_method="random",
            regex="[^？]+？|[^？]+$",
            content_cleanup_rule="",
        )
    source = Event("真实输入", direct=True)
    await consume(plugin.observe(source))
    await consume(plugin.participate(source))
    clock.advance(0)
    event = queue.get_nowait()
    saved = []

    async def agent(event):
        if mode == "tool_notice":
            event.set_result(event.plain_result("工具状态通知"))
            yield
        text = (
            "这是一段满足文转图条件的原生回复" * 8
            if mode == "t2i"
            else "现在好了？还能打开吗？"
        )
        async for result in native.answer(event, text=text, saved=saved):
            yield result

    await native.run(event, agent)
    assert saved == ["history saved"]
    assert event.is_stopped()
    assert (
        len(await plugin.storage.rows("SELECT * FROM messages WHERE direction='in'"))
        == 1
    )
    assert native.hooks
    if mode == "quote":
        assert isinstance(source.sent[0].chain[0], Reply)
    elif mode == "tts":
        assert isinstance(source.sent[0].chain[0], Record)
    elif mode == "t2i":
        assert isinstance(source.sent[0].chain[0], Image)
    elif mode == "segments":
        assert [chain.get_plain_text() for chain in source.sent] == [
            "现在好了？",
            "还能打开吗？",
        ]
    else:
        assert source.sent[0].get_plain_text() == "工具状态通知"
    assert event.get_extra("humanization_turn") is None


@pytest.mark.parametrize("mode, tag", [("tts", "record"), ("t2i", "image")])
async def test_native_media_conversion_and_recorder_tags(
    plugin, native, monkeypatch, mode, tag
):
    if mode == "tts":
        native.config["provider_tts_settings"].update(
            enable=True, dual_output=False, use_file_service=False
        )
        native.config["provider_tts_settings"]["trigger_probability"] = 1
        plugin.context.get_using_tts_provider_async = AsyncMock(
            return_value=SimpleNamespace(get_audio=AsyncMock(return_value="voice.wav"))
        )
        monkeypatch.setattr(
            SessionServiceManager,
            "should_process_tts_request",
            AsyncMock(return_value=True),
        )
    else:
        native.config["t2i"] = True
        native.config["t2i_word_threshold"] = 50
        monkeypatch.setattr(
            decorate_module.html_renderer,
            "render_t2i",
            AsyncMock(return_value="image.png"),
        )

    text = "这是一段满足原生转换条件的回复" * 8

    async def agent(event):
        async for result in native.answer(event, text=text):
            yield result

    event = Event(direct=True)
    await native.run(event, agent)
    component = Record if mode == "tts" else Image
    assert isinstance(event.sent[0].chain[0], component)
    assert len(native.hooks) == 1
    row = (await plugin.storage.rows("SELECT * FROM messages WHERE direction='out'"))[0]
    assert row["text"] == f"[{tag}]"
    assert "voice.wav" not in row["segments"] and "image.png" not in row["segments"]


async def test_native_segmentation_still_runs(plugin, native):
    native.config["platform_settings"]["segmented_reply"].update(
        enable=True,
        interval="0,0",
        interval_method="random",
        regex="[^？]+？|[^？]+$",
        content_cleanup_rule="",
    )

    async def agent(event):
        async for result in native.answer(event, text="现在好了？还能打开吗？"):
            yield result

    event = Event(direct=True)
    await native.run(event, agent)
    assert [chain.get_plain_text() for chain in event.sent] == [
        "现在好了？",
        "还能打开吗？",
    ]
    assert len(native.hooks) == 1


async def test_final_media_and_general_notifications_are_preserved(plugin, native):
    artifact = File(file="artifact.pdf", name="artifact.pdf")

    async def agent(event):
        event.set_result(event.plain_result("工具错误通知"))
        yield
        async for result in native.answer(
            event, media=MessageChain([Plain("看这个$已经整理好了"), artifact])
        ):
            yield result

    event = Event(direct=True)
    await native.run(event, agent)
    assert event.sent[0].get_plain_text() == "工具错误通知"
    assert [chain.get_plain_text() for chain in event.sent[1:]] == [
        "看这个",
        "已经整理好了",
    ]
    assert event.sent[-1].chain[-1] is artifact
    assert len(native.hooks) == 3


@pytest.mark.parametrize("late_hook", [False, True])
@pytest.mark.parametrize("scheduled", [False, True])
async def test_native_tool_loop_and_late_completion_hook_are_not_cut_short(
    plugin, native, late_hook, scheduled
):
    order = []

    async def agent(event):
        class Runner:
            streaming = False

            def __init__(self):
                self.run_context = SimpleNamespace(context=SimpleNamespace(event=event))
                self.finished = False
                self.index = 0

            def done(self):
                return self.finished

            def request_stop(self):
                pytest.fail("Agent unexpectedly stopped")

            async def step(self):
                self.index += 1
                if self.index == 1:
                    yield SimpleNamespace(
                        type="llm_result",
                        data={"chain": MessageChain().message("先查一下")},
                    )
                    order.append("tool called")
                    yield SimpleNamespace(
                        type="tool_call",
                        data={
                            "chain": MessageChain(
                                [Json(data={"name": "test_tool", "id": "1"})]
                            )
                        },
                    )
                    yield SimpleNamespace(
                        type="tool_call_result",
                        data={
                            "chain": MessageChain(
                                [Image(file="tool.png")], type="tool_direct_result"
                            )
                        },
                    )
                    return
                response = LLMResponse(role="assistant", completion_text="查到了$你看")
                if not late_hook:
                    await plugin.validate(event, response)
                yield SimpleNamespace(
                    type="llm_result",
                    data={"chain": MessageChain().message(response.completion_text)},
                )
                if late_hook:
                    await plugin.validate(event, response)
                self.finished = True

        async for result in run_agent(Runner(), show_tool_use=False):
            yield result
        order.append("history saved")

    event = Event(direct=True)
    if scheduled:
        from test_scheduling import Clock

        plugin.settings.controller["mode"] = "scheduled"
        queue = asyncio.Queue()
        plugin.context.get_event_queue = lambda: queue
        clock = Clock(time.time())
        plugin.scheduler.clock = clock
        plugin.scheduler.call_later = clock.later
        await consume(plugin.observe(event))
        await consume(plugin.participate(event))
        clock.advance(0)
        event = queue.get_nowait()
        sent = event.source.sent
    else:
        sent = event.sent
    await native.run(event, agent)
    assert order == ["tool called", "history saved"]
    assert isinstance(sent[0].chain[0], Image)
    assert [chain.get_plain_text() for chain in sent[1:]] == ["查到了", "你看"]
    assert len(native.hooks) == 2
    assert event.is_stopped() is scheduled


async def test_native_group_recorder_and_other_handlers_do_not_replay_scheduled_input(
    plugin, native
):
    from humanization_test.main import Humanization
    from test_scheduling import Clock

    from astrbot.builtin_stars.astrbot.main import Main

    plugin.settings.controller.update(mode="scheduled", group=1, force_at=False)
    queue = asyncio.Queue()
    plugin.context.get_event_queue = lambda: queue
    clock = Clock(time.time())
    plugin.scheduler.clock = clock
    plugin.scheduler.call_later = clock.later
    manager = SimpleNamespace(
        insert_message_chain=AsyncMock(return_value=SimpleNamespace(id=7))
    )
    recorder = SimpleNamespace(
        context=SimpleNamespace(
            get_config=lambda **kw: {
                "provider_ltm_settings": {"group_message_history_enable": True}
            },
            message_history_manager=manager,
        )
    )
    source = Event("original input")
    await Main.persist_group_message(recorder, source)
    await consume(plugin.observe(source))
    await consume(plugin.participate(source))
    clock.advance(0)
    event = queue.get_nowait()
    assert event.get_extra("_current_platform_message_history_id") == 7
    other_handler = AsyncMock()

    async def guard(event):
        async for result in Humanization.scheduled_event(
            SimpleNamespace(runtime=plugin), event
        ):
            yield result

    async def persist(event):
        await Main.persist_group_message(recorder, event)

    handlers = [
        native.metadata(name, handler)
        for name, handler in (
            ("guard", guard),
            ("persist", persist),
            ("other", other_handler),
        )
    ]
    for handler in handlers:
        handler.handler_full_name = handler.handler_name
    event.set_extra("activated_handlers", handlers)
    stage = StarRequestSubStage()
    assert await consume(stage.process(event)) == [None]
    assert event.is_stopped()
    manager.insert_message_chain.assert_awaited_once()
    other_handler.assert_not_awaited()
    assert len(await plugin.storage.rows("SELECT * FROM messages")) == 1


async def test_filter_failure_keeps_agent_history_and_releases_cache(plugin, native):
    plugin.adapter.generate = AsyncMock(return_value="还是\n不合法")
    saved = []

    async def agent(event):
        async for result in native.answer(event, text="第一行\n第二行", saved=saved):
            yield result

    event = Event(direct=True)
    await native.run(event, agent)
    assert saved == ["history saved"] and not event.is_stopped()
    assert not event.sent and not native.hooks
    assert event.get_extra("humanization_turn") is None
    assert (await plugin.storage.rows("SELECT * FROM reply_runs"))[0][
        "status"
    ] == "filtered"


async def test_other_decorator_can_veto_replay_without_resending(plugin, native):
    async def veto(event):
        event.clear_result()

    native.decorators.append(native.metadata("veto", veto))
    event = Event(direct=True)
    await native.run(event, native.answer)
    assert not event.sent and not native.hooks
    assert event.get_extra("humanization_turn") is None
