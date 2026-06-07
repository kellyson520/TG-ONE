import asyncio
import inspect

import pytest

from repositories import db_monitor


@pytest.mark.asyncio
async def test_start_database_monitoring_returns_and_tracks_task(monkeypatch):
    started = asyncio.Event()

    async def fake_start_monitoring(interval=60):
        assert interval == 60
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        db_monitor.db_monitor,
        "start_monitoring",
        fake_start_monitoring,
    )

    try:
        await asyncio.wait_for(
            db_monitor.start_database_monitoring(),
            timeout=0.05,
        )
        await asyncio.wait_for(started.wait(), timeout=0.05)

        assert db_monitor._monitoring_task is not None
        assert not db_monitor._monitoring_task.done()
    finally:
        stop_result = db_monitor.stop_database_monitoring()
        if inspect.isawaitable(stop_result):
            await stop_result
