import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.helpers.maintenance_gate import try_maintenance
from scheduler import db_archive_job


def test_db_archive_job_import_does_not_initialize_archive_system(monkeypatch):
    import repositories.archive_init as archive_init

    calls = []
    monkeypatch.setattr(
        archive_init,
        "init_archive_system",
        lambda: calls.append("init") or True,
    )

    importlib.reload(db_archive_job)

    assert calls == []


@pytest.mark.asyncio
async def test_archive_once_async_skips_when_maintenance_gate_is_busy(monkeypatch):
    manager = SimpleNamespace(run_archiving_cycle=AsyncMock())
    monkeypatch.setattr(db_archive_job, "get_archive_manager", lambda *_args, **_kwargs: manager)
    monkeypatch.setattr(db_archive_job, "_archive_system_checked", False, raising=False)
    calls = []
    monkeypatch.setattr(
        "repositories.archive_init.init_archive_system",
        lambda: calls.append("init") or True,
    )

    with try_maintenance("unit_test_busy") as acquired:
        assert acquired is True
        await db_archive_job.archive_once_async()

    manager.run_archiving_cycle.assert_not_called()
    assert calls == []


@pytest.mark.asyncio
async def test_archive_once_async_runs_when_maintenance_gate_is_free(monkeypatch):
    manager = SimpleNamespace(run_archiving_cycle=AsyncMock())
    monkeypatch.setattr(db_archive_job, "get_archive_manager", lambda *_args, **_kwargs: manager)
    monkeypatch.setattr(db_archive_job, "_archive_system_checked", False, raising=False)
    calls = []
    monkeypatch.setattr(
        "repositories.archive_init.init_archive_system",
        lambda: calls.append("init") or True,
    )

    await db_archive_job.archive_once_async()

    assert calls == ["init"]
    manager.run_archiving_cycle.assert_awaited_once()
