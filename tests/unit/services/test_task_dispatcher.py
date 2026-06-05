import asyncio

import pytest

from core.config import settings
from services.task_dispatcher import TaskDispatcher


@pytest.mark.asyncio
async def test_dispatcher_fetch_limit_respects_queue_capacity(monkeypatch):
    monkeypatch.setattr(settings, "TASK_DISPATCHER_BATCH_SIZE", 10)

    queue = asyncio.Queue(maxsize=3)
    queue.put_nowait(["existing-1"])
    queue.put_nowait(["existing-2"])

    class Repo:
        def __init__(self):
            self.fetch_limits = []

        async def fetch_next(self, limit=1):
            self.fetch_limits.append(limit)
            dispatcher.running = False
            return []

    repo = Repo()
    dispatcher = TaskDispatcher(repo, queue)
    dispatcher.running = True
    dispatcher.current_sleep = 0

    await dispatcher._dispatch_loop()

    assert repo.fetch_limits == [1]


def test_dispatcher_unbounded_queue_uses_batch_size(monkeypatch):
    monkeypatch.setattr(settings, "TASK_DISPATCHER_BATCH_SIZE", 7)

    dispatcher = TaskDispatcher(repo=None, queue=asyncio.Queue(maxsize=0))

    assert dispatcher._available_queue_slots() == 7
