import logging
import asyncio
import builtins

import pytest

import core.db_factory as db_factory
from core.database import Database


class RollbackFailingSession:
    def in_transaction(self):
        return True

    async def rollback(self):
        raise RuntimeError("rollback unavailable")

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_database_session_logs_rollback_failure(caplog):
    session = RollbackFailingSession()
    db = Database.__new__(Database)
    db._write_factory = lambda: session
    db._read_factory = lambda: session

    caplog.set_level(logging.WARNING, logger="core.database")

    with pytest.raises(ValueError, match="unit failure"):
        async with db.session():
            raise ValueError("unit failure")

    assert "[Database] 事务回滚失败" in caplog.text
    assert "rollback unavailable" in caplog.text


class ClosingFailingSession:
    def in_transaction(self):
        return True

    async def rollback(self):
        raise RuntimeError("rollback during cancel unavailable")

    async def close(self):
        raise RuntimeError("close during cancel unavailable")


class FakeAsyncSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_async_session_manager_logs_cancel_cleanup_failures(
    monkeypatch,
    caplog,
):
    session = ClosingFailingSession()

    class FakeSessionFactory:
        def __call__(self):
            return FakeAsyncSessionContext(session)

    monkeypatch.setattr(
        db_factory,
        "get_async_session_factory",
        lambda readonly=False: FakeSessionFactory(),
    )
    caplog.set_level(logging.DEBUG, logger="core.db_factory")

    with pytest.raises(asyncio.CancelledError):
        async with db_factory.AsyncSessionManager():
            raise asyncio.CancelledError()

    assert "AsyncSessionManager rollback failed during cancellation" in caplog.text
    assert "rollback during cancel unavailable" in caplog.text
    assert "AsyncSessionManager close failed during cleanup" in caplog.text
    assert "close during cancel unavailable" in caplog.text


class CleanupResult:
    rowcount = 1


class CleanupSession:
    def __init__(self):
        self.execute_count = 0
        self.commits = 0

    async def execute(self, stmt):
        self.execute_count += 1
        return CleanupResult()

    async def commit(self):
        self.commits += 1


async def test_async_cleanup_old_logs_logs_missing_stats_manager(
    monkeypatch,
    caplog,
):
    session = CleanupSession()
    original_import = builtins.__import__

    class ComparableColumn:
        def __lt__(self, other):
            return True

    class FakeLogModel:
        created_at = ComparableColumn()

    class FakeDelete:
        def where(self, condition):
            return self

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sqlalchemy" and "delete" in fromlist:
            class FakeSqlAlchemy:
                @staticmethod
                def delete(model):
                    return FakeDelete()

            return FakeSqlAlchemy()
        if name == "models.models":
            class FakeModels:
                RuleLog = FakeLogModel
                ErrorLog = FakeLogModel
                AuditLog = FakeLogModel

            return FakeModels()
        if name == "core.stats_manager":
            raise ImportError("stats manager unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(
        db_factory,
        "AsyncSessionManager",
        lambda *args, **kwargs: FakeAsyncSessionContext(session),
    )
    monkeypatch.setattr(builtins, "__import__", fake_import)
    caplog.set_level(logging.DEBUG, logger="core.db_factory")

    deleted = await db_factory.async_cleanup_old_logs(days=7)

    assert deleted == 3
    assert session.commits == 1
    assert "清理统计模块不可用" in caplog.text
    assert "stats manager unavailable" in caplog.text
