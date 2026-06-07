from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from models.models import RuleLog
from repositories.archive_manager import ArchiveManager


class _AsyncSession:
    def __init__(self):
        self.execute = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _result_with_scalar(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _result_with_rows(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_archive_writes_cross_date_batch_to_separate_partitions(monkeypatch):
    session = _AsyncSession()
    older = datetime(2026, 4, 1, 12, 0, 0)
    newer = datetime(2026, 4, 2, 12, 0, 0)
    rows = [
        RuleLog(id=1, rule_id=10, action="forwarded", details="older", created_at=older),
        RuleLog(id=2, rule_id=10, action="forwarded", details="newer", created_at=newer),
    ]

    session.execute.side_effect = [
        _result_with_scalar(2),
        _result_with_rows(rows),
        MagicMock(),
    ]
    monkeypatch.setattr("repositories.archive_manager.settings.ARCHIVE_BATCH_SIZE", 100, raising=False)

    manager = ArchiveManager(lambda: session)

    with patch("repositories.archive_manager.write_parquet", return_value="/tmp/archive/part.parquet") as write_mock:
        await manager.archive_model_data(RuleLog, days_threshold=30)

    assert write_mock.call_count == 2
    calls_by_date = {
        call.kwargs["partition_dt"].date(): [row["id"] for row in call.args[1]]
        for call in write_mock.call_args_list
    }
    assert calls_by_date == {
        older.date(): [1],
        newer.date(): [2],
    }


@pytest.mark.asyncio
async def test_archive_stops_after_delete_lock_to_avoid_duplicate_parquet_writes(monkeypatch):
    session = _AsyncSession()
    old_time = datetime.utcnow() - timedelta(days=40)
    row = RuleLog(
        id=1,
        rule_id=10,
        action="forwarded",
        details="archive lock regression",
        created_at=old_time,
    )
    locked = OperationalError("DELETE FROM rule_logs", {}, Exception("database is locked"))

    call_count = 0

    async def execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _result_with_scalar(2)
        if call_count in (2, 8):
            return _result_with_rows([row])
        raise locked

    session.execute.side_effect = execute_side_effect
    monkeypatch.setattr("repositories.archive_manager.settings.ARCHIVE_BATCH_SIZE", 1, raising=False)
    monkeypatch.setattr("repositories.archive_manager.asyncio.sleep", AsyncMock())

    manager = ArchiveManager(lambda: session)

    with patch("repositories.archive_manager.write_parquet", return_value="/tmp/archive/part.parquet") as write_mock:
        await manager.archive_model_data(RuleLog, days_threshold=30)

    write_mock.assert_called_once()
