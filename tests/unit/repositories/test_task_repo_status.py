import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import core.db_factory as db_factory

from repositories.task_repo import TaskRepository


class FakeQueueStatusSession:
    def __init__(self):
        self.execute_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.execute_count += 1
        if self.execute_count == 1:
            return SimpleNamespace(all=lambda: [("completed", 1)])
        raise RuntimeError("delay query failed")


class FakeDB:
    def __init__(self, session):
        self.session = session

    def get_session(self, readonly=False):
        return self.session


class FakePushSession:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.commits = 0

    async def execute(self, stmt):
        return SimpleNamespace(rowcount=self.rowcount)

    async def commit(self):
        self.commits += 1


class FakePushSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_pending_task_listener_duplicate_unsubscribe_is_observable(caplog):
    repo = TaskRepository(FakeDB(session=None))
    callback = lambda: None
    unsubscribe = repo.register_pending_task_listener(callback)

    unsubscribe()
    caplog.set_level(logging.DEBUG, logger="repositories.task_repo")
    unsubscribe()

    assert "待处理任务监听器已不存在" in caplog.text


@pytest.mark.asyncio
async def test_get_queue_status_logs_avg_delay_failure(caplog):
    session = FakeQueueStatusSession()
    repo = TaskRepository(FakeDB(session))
    caplog.set_level(logging.WARNING, logger="repositories.task_repo")

    status = await repo.get_queue_status()

    assert status["completed_tasks"] == 1
    assert status["avg_delay"] == "0.0s"
    assert "队列平均延迟统计失败" in caplog.text
    assert "delay query failed" in caplog.text


@pytest.mark.asyncio
async def test_push_notifies_pending_task_listener_after_insert(monkeypatch):
    session = FakePushSession(rowcount=1)
    monkeypatch.setattr(
        db_factory,
        "AsyncSessionManager",
        lambda *args, **kwargs: FakePushSessionContext(session),
    )
    repo = TaskRepository(FakeDB(session=None))
    notifications = []

    repo.register_pending_task_listener(lambda: notifications.append("wake"))

    await repo.push(
        task_type="process_message",
        payload={"chat_id": 1001, "message_id": 42},
    )

    assert session.commits == 1
    assert notifications == ["wake"]


@pytest.mark.asyncio
async def test_push_does_not_notify_listener_when_insert_is_ignored(monkeypatch):
    session = FakePushSession(rowcount=0)
    monkeypatch.setattr(
        db_factory,
        "AsyncSessionManager",
        lambda *args, **kwargs: FakePushSessionContext(session),
    )
    repo = TaskRepository(FakeDB(session=None))
    notifications = []

    repo.register_pending_task_listener(lambda: notifications.append("wake"))

    await repo.push(
        task_type="process_message",
        payload={"chat_id": 1001, "message_id": 42},
    )

    assert session.commits == 1
    assert notifications == []


@pytest.mark.asyncio
async def test_push_does_not_notify_listener_for_future_scheduled_task(
    monkeypatch,
):
    session = FakePushSession(rowcount=1)
    monkeypatch.setattr(
        db_factory,
        "AsyncSessionManager",
        lambda *args, **kwargs: FakePushSessionContext(session),
    )
    repo = TaskRepository(FakeDB(session=None))
    notifications = []

    repo.register_pending_task_listener(lambda: notifications.append("wake"))

    await repo.push(
        task_type="message_delete",
        payload={"chat_id": 1001, "message_id": 42},
        scheduled_at=datetime.utcnow() + timedelta(hours=1),
    )

    assert session.commits == 1
    assert notifications == []


@pytest.mark.asyncio
async def test_push_batch_notifies_listener_when_rowcount_is_unknown(
    monkeypatch,
):
    session = FakePushSession(rowcount=None)
    monkeypatch.setattr(
        db_factory,
        "AsyncSessionManager",
        lambda *args, **kwargs: FakePushSessionContext(session),
    )
    repo = TaskRepository(FakeDB(session=None))
    notifications = []

    repo.register_pending_task_listener(lambda: notifications.append("wake"))

    await repo.push_batch([
        ("process_message", {"chat_id": 1001, "message_id": 42}, 0),
    ])

    assert notifications == ["wake"]
