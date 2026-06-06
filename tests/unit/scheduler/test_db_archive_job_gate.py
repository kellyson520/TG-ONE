from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.helpers.maintenance_gate import try_maintenance
from scheduler import db_archive_job


@pytest.mark.asyncio
async def test_archive_once_async_skips_when_maintenance_gate_is_busy(monkeypatch):
    manager = SimpleNamespace(run_archiving_cycle=AsyncMock())
    monkeypatch.setattr(db_archive_job, "get_archive_manager", lambda *_args, **_kwargs: manager)

    with try_maintenance("unit_test_busy") as acquired:
        assert acquired is True
        await db_archive_job.archive_once_async()

    manager.run_archiving_cycle.assert_not_called()


@pytest.mark.asyncio
async def test_archive_once_async_runs_when_maintenance_gate_is_free(monkeypatch):
    manager = SimpleNamespace(run_archiving_cycle=AsyncMock())
    monkeypatch.setattr(db_archive_job, "get_archive_manager", lambda *_args, **_kwargs: manager)

    await db_archive_job.archive_once_async()

    manager.run_archiving_cycle.assert_awaited_once()
