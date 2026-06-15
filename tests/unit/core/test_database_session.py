import logging
import asyncio
import sys
import types

import pytest

import core.db_factory as db_factory
from core.database import Database


class _ImportBlocker(types.ModuleType):
    """Module proxy that raises ImportError on any public attribute access.

    Used to simulate missing optional modules in tests without
    monkeypatching builtins.__import__.
    """

    def __init__(self, name: str, error_msg: str = ""):
        super().__init__(name)
        self.__dict__["_error_msg"] = error_msg
        self.__path__ = []  # mark as a package to prevent sub-module lookup

    def __getattr__(self, attr: str):
        if attr.startswith("_") and attr != "__path__":
            raise AttributeError(attr)
        raise ImportError(self._error_msg)


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

    class ComparableColumn:
        def __lt__(self, other):
            return True

    class FakeLogModel:
        created_at = ComparableColumn()

    class FakeDelete:
        def where(self, condition):
            return self

    # Provide a fake sqlalchemy.delete so the function can build statements
    import sqlalchemy as _sa

    monkeypatch.setattr(_sa, "delete", lambda model: FakeDelete())

    # Provide fake models.models with the required log model classes
    fake_models_mod = types.ModuleType("models.models")
    fake_models_mod.RuleLog = FakeLogModel
    fake_models_mod.ErrorLog = FakeLogModel
    fake_models_mod.AuditLog = FakeLogModel
    monkeypatch.setitem(sys.modules, "models.models", fake_models_mod)

    # Simulate missing core.stats_manager via sys.modules
    monkeypatch.setitem(
        sys.modules,
        "core.stats_manager",
        _ImportBlocker("core.stats_manager", "stats manager unavailable"),
    )

    monkeypatch.setattr(
        db_factory,
        "AsyncSessionManager",
        lambda *args, **kwargs: FakeAsyncSessionContext(session),
    )
    caplog.set_level(logging.DEBUG, logger="core.db_factory")

    deleted = await db_factory.async_cleanup_old_logs(days=7)

    assert deleted == 3
    assert session.commits == 1
    assert "清理统计模块不可用" in caplog.text
    assert "stats manager unavailable" in caplog.text
