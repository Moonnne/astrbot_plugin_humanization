"""Incremental diary persistence, evidence checks and bounded observation."""

import json
import sqlite3
from dataclasses import replace
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from diary_helpers import model_change, topic_change
from humanization_test.core.recorder.summarizer import Summarizer
from humanization_test.core.settings import Settings
from test_runtime import message
from test_runtime import storage as storage


async def test_incremental_topics_and_partial_update_preserve_other_fields(
    storage, config, log
):
    settings = Settings(config)
    generate = AsyncMock(return_value=model_change("讨论供暖", 1))
    worker = Summarizer(storage, settings, generate, "system", log)
    await storage.append(message(1))
    await worker.summarize(
        await storage.session("group"), await storage.recent("group", 10)
    )
    original = (await storage.diaries("group"))[0]["topics"][0]
    await storage.append(message(2))
    await storage.append(replace(message(3), direction="out"))
    second = json.loads(model_change("周末搬家", 2))["changes"][0]
    generate.return_value = json.dumps(
        {
            "changes": [
                second,
                {
                    "action": "update",
                    "id": original["id"],
                    "evidence_seqs": [3],
                    "reply": "我认同最近很冷。",
                },
            ]
        }
    )
    await worker.summarize(
        await storage.session("group"),
        await storage.rows("SELECT * FROM messages WHERE seq>1 ORDER BY seq"),
    )
    topics = (await storage.diaries("group"))[0]["topics"]
    assert len(topics) == 2
    updated = next(topic for topic in topics if topic["id"] == original["id"])
    assert updated == original | {"reply": "我认同最近很冷。", "last_seq": 3}
    assert (await storage.session("group"))["cursor"] == 3
    payload = json.loads(generate.call_args.args[2])
    assert payload["messages"][0]["local_time"].endswith("+0800")
    assert "body" not in payload["existing_diaries"][0]
    assert payload["output_char_limit"] == 6000


@pytest.mark.parametrize(
    "bad",
    [
        "not JSON",
        '{"changes":{},"extra":1}',
        '{"changes":[{"action":"delete","id":1}]}',
        '{"changes":[{"action":"update","id":999,"evidence_seqs":[2],"topic":"x"}]}',
        '{"changes":[{"action":"add","evidence_seqs":[2],"topic":"missing fields"}]}',
        model_change("invalid evidence", 99),
        model_change("only old evidence", 1),
    ],
)
async def test_invalid_batch_preserves_progress_and_all_topics(
    storage, config, log, bad
):
    settings = Settings(config)
    day = datetime.now(settings.timezone).date().isoformat()
    await storage.append(message(1))
    await storage.commit_summary("group", day, [topic_change("old")], 1, 1, 1)
    await storage.append(message(2))
    before = await storage.diaries("group")
    worker = Summarizer(storage, settings, AsyncMock(return_value=bad), "system", log)
    with pytest.raises(ValueError):
        await worker.summarize(
            await storage.session("group"),
            await storage.rows("SELECT * FROM messages WHERE seq=2"),
        )
    assert await storage.diaries("group") == before
    assert (await storage.session("group"))["cursor"] == 1


@pytest.mark.parametrize(
    "target_kind", ["other_scope", "sealed", "omitted", "duplicate"]
)
async def test_update_must_target_one_visible_writable_topic(
    storage, config, log, target_kind
):
    settings = Settings(config)
    day = datetime.now(settings.timezone).date().isoformat()
    await storage.append(message(1))
    target_scope = "other" if target_kind == "other_scope" else "group"
    target_day = "2000-01-01" if target_kind == "sealed" else day
    await storage.commit_summary(
        target_scope, target_day, [topic_change("target")], 1, 1, 1
    )
    if target_kind == "sealed":
        await storage.seal_before(day)
    if target_kind == "omitted":
        settings.recorder["diary_context_chars"] = 1
    target = (await storage.rows("SELECT id FROM diary_topics"))[0]["id"]
    change = {
        "action": "update",
        "id": target,
        "evidence_seqs": [2],
        "reaction": "认可",
    }
    await storage.append(message(2))
    worker = Summarizer(
        storage,
        settings,
        AsyncMock(
            return_value=json.dumps(
                {
                    "changes": [change, change]
                    if target_kind == "duplicate"
                    else [change]
                }
            )
        ),
        "system",
        log,
    )
    before = await storage.rows("SELECT * FROM diary_topics")
    with pytest.raises(ValueError):
        await worker.summarize(
            await storage.session("group"), await storage.recent("group", 10)
        )
    assert await storage.rows("SELECT * FROM diary_topics") == before


async def test_valid_add_followed_by_invalid_update_is_not_partially_saved(
    storage, config, log
):
    settings = Settings(config)
    await storage.append(message(1))
    data = json.loads(model_change("must not persist"))
    data["changes"].append(
        {"action": "update", "id": 999, "evidence_seqs": [1], "reply": "x"}
    )
    worker = Summarizer(
        storage, settings, AsyncMock(return_value=json.dumps(data)), "system", log
    )
    with pytest.raises(ValueError):
        await worker.summarize(
            await storage.session("group"), await storage.recent("group", 10)
        )
    assert not await storage.rows("SELECT * FROM diary_topics")
    assert not await storage.rows("SELECT * FROM diary_days")
    assert (await storage.session("group"))["cursor"] == 0


async def test_database_error_rolls_back_topics_day_and_cursor(storage):
    await storage.append(message(1))
    await storage.commit_summary("group", "2026-10-15", [topic_change("old")], 1, 1, 1)
    before = await storage.diaries("group")
    await storage.db.execute(
        "CREATE TRIGGER reject_topic BEFORE INSERT ON diary_topics "
        "WHEN NEW.topic='fail' BEGIN SELECT RAISE(ABORT,'test failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        await storage.commit_summary(
            "group", "2026-10-16", [topic_change("new"), topic_change("fail")], 2, 2, 2
        )
    assert await storage.diaries("group") == before
    assert (await storage.session("group"))["cursor"] == 1


async def test_empty_batch_advances_without_creating_visible_diary(
    storage, config, log
):
    await storage.append(message(1))
    worker = Summarizer(
        storage,
        Settings(config),
        AsyncMock(return_value='{"changes":[]}'),
        "system",
        log,
    )
    await worker.summarize(
        await storage.session("group"), await storage.recent("group", 10)
    )
    assert (await storage.session("group"))["cursor"] == 1
    assert not await storage.diaries("group")
    assert not await storage.rows("SELECT * FROM diary_topics")


async def test_oversized_result_is_rejected_without_truncation(storage, config, log):
    config["recorder"]["summary_output_chars"] = 100
    await storage.append(message(1))
    worker = Summarizer(
        storage,
        Settings(config),
        AsyncMock(return_value=model_change("x" * 300)),
        "system",
        log,
    )
    with pytest.raises(ValueError, match="limit"):
        await worker.summarize(
            await storage.session("group"), await storage.recent("group", 10)
        )
    assert not await storage.rows("SELECT * FROM diary_topics")
    assert (await storage.session("group"))["cursor"] == 0


async def test_context_selects_complete_recently_updated_topics_without_deleting(
    storage,
):
    await storage.append(message(1))
    await storage.commit_summary(
        "group", "2026-10-15", [topic_change("A"), topic_change("B", 2)], 1, 1, 1
    )
    full = await storage.diaries("group")
    a, b = full[0]["topics"]
    budget = len(json.dumps(a, ensure_ascii=False, separators=(",", ":")))
    await storage.commit_summary(
        "group",
        "2026-10-15",
        [
            {
                "action": "update",
                "id": a["id"],
                "first_seq": 3,
                "last_seq": 3,
                "reaction": "赞同",
            }
        ],
        3,
        3,
        2,
    )
    limited = (await storage.diaries("group", budget=budget))[0]
    assert [t["id"] for t in limited["topics"]] == [a["id"]]
    assert limited["omitted_topics"] == 1
    assert "[Context]" in limited["body"]
    assert "[Reaction]赞同" in limited["body"]
    assert len((await storage.diaries("group"))[0]["topics"]) == 2
    assert (await storage.diaries("group", budget=1))[0]["topics"] == []
    assert b in (await storage.diaries("group"))[0]["topics"]


async def test_gap_persists_and_day_reset_cascades_without_removing_other_days(storage):
    await storage.append(message(1))
    await storage.commit_summary("group", "2026-10-14", [topic_change("old")], 1, 1, 1)
    await storage.commit_summary(
        "group", "2026-10-15", [topic_change("new")], 2, 2, 2, coverage_gap=True
    )
    await storage.commit_summary("group", "2026-10-15", [], 3, 3, 3)
    assert (await storage.diaries("group"))[-1]["coverage_gap"] == 1
    await storage.reset("group", "2026-10-15")
    assert [
        row["day"] for row in await storage.rows("SELECT day FROM diary_topics")
    ] == ["2026-10-14"]
    await storage.reset_all()
    assert not await storage.rows("SELECT * FROM diary_topics")


@pytest.mark.parametrize("key", ["diary_context_chars", "summary_output_chars"])
@pytest.mark.parametrize("value", [0, -1, True, 0.5])
def test_diary_budgets_must_be_positive_integers(config, key, value):
    config["recorder"][key] = value
    with pytest.raises(ValueError, match=key):
        Settings(config)


async def test_latest_dates_share_budget_and_persist_across_restart(storage):
    await storage.append(message(1))
    for index, day in enumerate(("2026-10-13", "2026-10-14", "2026-10-15"), 1):
        await storage.commit_summary(
            "group", day, [topic_change(day, index)], index, index, index
        )
    full = await storage.diaries("group")
    assert [day["day"] for day in full] == ["2026-10-14", "2026-10-15"]
    latest = full[-1]["topics"][0]
    budget = len(json.dumps(latest, ensure_ascii=False, separators=(",", ":")))
    limited = await storage.diaries("group", budget=budget)
    assert limited[0]["topics"] == [] and limited[0]["omitted_topics"] == 1
    assert limited[-1]["topics"] == [latest]
    await storage.close()
    await storage.open()
    assert await storage.diaries("group") == full
    assert len(await storage.rows("SELECT * FROM diary_topics")) == 3


async def test_input_truncation_keeps_date_first_and_records_gap(storage, config, log):
    config["recorder"]["context_chars"] = 400
    await storage.append(replace(message(1), text="x" * 600))
    worker = Summarizer(
        storage,
        Settings(config),
        AsyncMock(return_value=model_change("短句")),
        "system",
        log,
    )
    await worker.summarize(
        await storage.session("group"), await storage.recent("group", 10)
    )
    payload = json.loads(worker.generate.call_args.args[2])
    assert payload["coverage_gap"] is True
    assert payload["messages"][0]["text"].endswith("[内容截断]")
    diary = (await storage.diaries("group"))[0]
    assert diary["body"].startswith(f"# {diary['day']}\n")
    assert "[Coverage]" in diary["body"]
