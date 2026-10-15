"""Exercise real SQLite isolation, cancellation and shutdown in temporary files."""

import ast
import asyncio
import re
from pathlib import Path
from unittest.mock import Mock

import aiosqlite
import pytest
from humanization_test.utils.database import Database
from test_runtime import message
from test_runtime import storage as storage


async def test_reader_cannot_see_uncommitted_write_and_cancel_rolls_back(storage):
    await storage.append(message(1))
    written = asyncio.Event()

    async def interrupted():
        async with storage.database.transaction() as tx:
            await tx.execute("UPDATE sessions SET human_count=99 WHERE scope='group'")
            written.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(interrupted())
    await written.wait()
    try:
        assert (await storage.session("group"))["human_count"] == 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    await storage.append(message(2))
    assert (await storage.session("group"))["human_count"] == 2


async def test_concurrent_duplicate_writes_preserve_counts_and_retention(storage):
    inserted = await asyncio.gather(*(storage.append(message(1)) for _ in range(12)))
    assert sum(inserted) == 1
    await asyncio.gather(*(storage.append(message(i)) for i in range(2, 22)))
    session = await storage.session("group")
    assert session["last_seq"] == session["human_count"] == 21
    assert await storage.message_count("group") == storage.retention
    assert [row["seq"] for row in await storage.recent("group", 5)] == list(
        range(17, 22)
    )


async def test_bounded_read_pool_keeps_snapshot_while_writer_progresses(storage):
    await storage.append(message(1))
    query = "SELECT COUNT(*) AS n FROM messages"
    async with (
        storage.database.snapshot() as first,
        storage.database.snapshot() as second,
    ):
        assert (await first.rows(query))[0]["n"] == 1
        assert (await second.rows(query))[0]["n"] == 1
        waiting = asyncio.create_task(storage.rows(query))
        await asyncio.sleep(0)
        assert not waiting.done()
        # A full reader pool must not block the independent writer.
        await asyncio.wait_for(storage.append(message(2)), 2)
        assert (await first.rows(query))[0]["n"] == 1
        assert (await second.rows(query))[0]["n"] == 1
        with pytest.raises(aiosqlite.OperationalError, match="readonly"):
            await first.execute("DELETE FROM messages")
    assert (await asyncio.wait_for(waiting, 2))[0]["n"] == 2


async def test_close_drains_accepted_leases_and_rejects_new_work(storage):
    await storage.append(message(1))
    entered = asyncio.Event()
    release = asyncio.Event()

    async def writer():
        async with storage.database.transaction() as tx:
            await tx.execute("UPDATE sessions SET last_reply=123 WHERE scope='group'")
            entered.set()
            await release.wait()

    active = asyncio.create_task(writer())
    await entered.wait()
    queued = asyncio.create_task(storage.append(message(2)))
    await asyncio.sleep(0)
    closing = asyncio.create_task(storage.close())
    async with storage.database._condition:
        await storage.database._condition.wait_for(
            lambda: storage.database._state == "closing"
        )
    try:
        assert not closing.done()
        with pytest.raises(RuntimeError, match="not accepting"):
            await storage.recent("group", 5)
    finally:
        release.set()
        await asyncio.gather(active, queued, closing)
    # With no external owner, the final connection cleans both auxiliary files.
    assert not Path(str(storage.path) + "-wal").exists()
    assert not Path(str(storage.path) + "-shm").exists()
    await storage.open()
    assert await storage.message_count("group") == 2
    assert (await storage.session("group"))["last_reply"] == 123


async def test_cancelled_close_still_completes_cleanup(storage):
    await storage.append(message(1))
    async with storage.database.snapshot() as tx:
        await tx.rows("SELECT * FROM messages")
        closing = asyncio.create_task(storage.close())
        async with storage.database._condition:
            await storage.database._condition.wait_for(
                lambda: storage.database._state == "closing"
            )
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()
    with pytest.raises(asyncio.CancelledError):
        await closing
    assert not Path(str(storage.path) + "-wal").exists()
    await storage.open()
    assert await storage.message_count("group") == 1


async def test_external_snapshot_reports_busy_without_discarding_wal(storage):
    await storage.append(message(1))
    async with aiosqlite.connect(storage.path, isolation_level=None) as external:
        async with external.execute("BEGIN"):
            pass
        async with external.execute("SELECT * FROM messages") as cursor:
            await cursor.fetchall()
        await storage.append(message(2))
        async with storage.database.transaction() as tx:
            await tx.execute("PRAGMA busy_timeout=1")
        storage.database.log = Mock()
        await storage.close()
        storage.database.log.info.assert_called_once()
        assert storage.database.log.info.call_args.kwargs["busy"] == 1
        assert Path(str(storage.path) + "-wal").exists()
        await external.rollback()
    await storage.open()
    assert await storage.message_count("group") == 2


async def test_initialization_error_releases_connections(tmp_path):
    database = Database(tmp_path / "invalid.sqlite3")
    database.sql.statements["schema.create"] = "INVALID SQL"
    with pytest.raises(aiosqlite.OperationalError):
        await database.open()
    assert not database._connections
    assert database._state == "closed"


def test_runtime_sql_is_packaged_as_resources():
    root = Path(__file__).resolve().parents[1]
    for directory in ("core", "utils"):
        for path in (root / directory).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert not re.match(
                        r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\s",
                        node.value,
                    ), path
