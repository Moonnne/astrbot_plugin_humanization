"""Media ownership, batching and fallback contracts using isolated files."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from humanization_test.core.recorder.media import Media
from test_runtime import message
from test_runtime import storage as storage


def service(storage, tmp_path, enabled=True):
    settings = SimpleNamespace(
        recorder={"media_enabled": enabled, "summary_provider": "recorder"},
        scope_action=lambda *args: "active",
    )
    context = SimpleNamespace(
        get_provider_by_id=lambda _: SimpleNamespace(
            provider_config={"modalities": ["image", "audio"]}
        ),
        llm_generate=AsyncMock(),
        get_platform_inst=lambda _: None,
        get_using_stt_provider_async=AsyncMock(return_value=None),
    )
    media = Media(storage, settings, context, Mock())
    media.root = tmp_path / "media"
    return media


async def add(media, tmp_path, index, kind="image", text=""):
    source = tmp_path / f"input{index}.bin"
    source.write_bytes(b"content")
    msg = replace(message(index), segments=json.dumps([{"type": kind}]))
    await media.storage.append(msg)
    await media.capture(
        msg,
        [
            SimpleNamespace(
                type=kind,
                name="picture.png",
                text=text,
                convert_to_file_path=AsyncMock(return_value=str(source)),
            )
        ],
    )
    return (
        await media.storage.rows(
            media.storage.sql["resources.for_message"],
            ((await media.storage.recent("group", 1))[0]["id"],),
        )
    )[0]


async def test_disabled_capture_and_retention_cleanup(storage, tmp_path):
    media = service(storage, tmp_path, False)
    row = await add(media, tmp_path, 1)
    path = media.path(row["path"])
    assert path.read_bytes() == b"content"
    assert row["status"] == "skipped"
    for index in range(2, 8):
        await storage.append(message(index))
    assert (
        await storage.rows(storage.sql["resources.for_message"], (row["message_row"],))
        == []
    )
    await media.cleanup()
    assert not path.exists()
    assert (tmp_path / "input1.bin").exists()
    media.context.llm_generate.assert_not_called()


async def test_multiple_images_one_request_and_reset(storage, tmp_path):
    media = service(storage, tmp_path)
    first = await add(media, tmp_path, 1)
    second = await add(media, tmp_path, 2)
    media.context.llm_generate.return_value = SimpleNamespace(
        completion_text=json.dumps({first["id"]: "海岸", second["id"]: "森林"})
    )
    rows = await storage.rows(storage.sql["resources.pending"])
    await media.batch(rows)
    media.context.llm_generate.assert_awaited_once()
    assert len(media.context.llm_generate.call_args.kwargs["image_urls"]) == 2
    assert "海岸" in (await storage.recent("group", 2))[0]["text"]
    assert (await storage.session("group"))["human_count"] == 2
    await storage.reset("group")
    await media.cleanup()
    assert not media.path(first["path"]).exists()


async def test_tts_text_and_no_visual_provider(storage, tmp_path):
    media = service(storage, tmp_path)
    audio = await add(media, tmp_path, 1, "record", "你好")
    assert audio["description"] == "你好" and audio["status"] == "ready"
    await add(media, tmp_path, 2)
    media.context.get_provider_by_id = lambda _: SimpleNamespace(
        provider_config={"modalities": ["text"]}
    )
    await media.batch(await storage.rows(storage.sql["resources.pending"]))
    media.context.llm_generate.assert_not_called()
    assert "picture.png" in (await storage.recent("group", 1))[0]["text"]


async def test_late_result_cannot_restore_deleted_message(storage, tmp_path):
    media = service(storage, tmp_path)
    row = await add(media, tmp_path, 1)
    await storage.reset("group")
    await media.finish(row, "迟到的结果")
    assert await storage.recent("group", 1) == []
    await media.cleanup()
    assert not media.path(row["path"]).exists()


async def test_adapter_stt_precedes_model(storage, tmp_path):
    media = service(storage, tmp_path)
    await add(media, tmp_path, 1, "record")
    media.action = AsyncMock(return_value={"text": "适配器转写"})
    await media.batch(await storage.rows(storage.sql["resources.pending"]))
    media.context.llm_generate.assert_not_called()
    media.context.get_using_stt_provider_async.assert_not_called()
    assert "适配器转写" in (await storage.recent("group", 1))[0]["text"]


async def test_native_stt_fallback_after_model_failure(storage, tmp_path):
    media = service(storage, tmp_path)
    await add(media, tmp_path, 1, "record")
    media.context.llm_generate.side_effect = RuntimeError("unavailable")
    native = SimpleNamespace(get_text=AsyncMock(return_value="原生转写"))
    media.context.get_using_stt_provider_async.return_value = native
    await media.batch(await storage.rows(storage.sql["resources.pending"]))
    media.context.llm_generate.assert_awaited_once()
    native.get_text.assert_awaited_once()
    assert "原生转写" in (await storage.recent("group", 1))[0]["text"]


async def test_plain_link_is_indexed_without_network_or_model(storage, tmp_path):
    media = service(storage, tmp_path)
    text = "看 https://example.com/article"
    msg = replace(
        message(1), text=text, segments=json.dumps([{"type": "text", "text": text}])
    )
    await storage.append(msg)
    await media.capture(msg, [SimpleNamespace(type="plain", text=text)])
    assert "[link:" in (await storage.recent("group", 1))[0]["text"]
    assert not await media.waiting(msg.scope)
    media.context.llm_generate.assert_not_called()
