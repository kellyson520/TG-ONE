import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_stop_logs_cancelled_dispatch_task(caplog):
    dispatcher = TaskDispatcher(repo=None, queue=asyncio.Queue())

    async def pending_loop():
        await asyncio.Event().wait()

    dispatcher.running = True
    dispatcher._task = asyncio.create_task(pending_loop())
    await asyncio.sleep(0)
    caplog.set_level("DEBUG", logger="services.task_dispatcher")

    await dispatcher.stop()

    assert "TaskDispatcher 停止时取消后台任务" in caplog.text


@pytest.mark.asyncio
async def test_dispatcher_backpressure_wait_uses_wake_event_not_sleep(monkeypatch):
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait(["existing"])
    repo = SimpleNamespace(fetch_next=AsyncMock())
    dispatcher = TaskDispatcher(repo=repo, queue=queue)
    dispatcher.running = True
    wait_timeouts = []

    async def fake_wait_for(awaitable, timeout):
        wait_timeouts.append(timeout)
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.CancelledError

    async def fake_sleep(_delay):
        raise asyncio.CancelledError

    monkeypatch.setattr("services.task_dispatcher.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr("services.task_dispatcher.asyncio.sleep", fake_sleep)

    await dispatcher._dispatch_loop()

    assert wait_timeouts == [pytest.approx(1.0)]
    repo.fetch_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_wait_for_queue_slot_timeout_is_observable(monkeypatch, caplog):
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait(["existing"])
    dispatcher = TaskDispatcher(repo=None, queue=queue)

    async def fake_wait_for(awaitable, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr("services.task_dispatcher.asyncio.wait_for", fake_wait_for)
    caplog.set_level("DEBUG", logger="services.task_dispatcher")

    await dispatcher._wait_for_queue_slot()

    assert "Dispatcher 背压等待超时" in caplog.text


@pytest.mark.asyncio
async def test_prefetch_entities_logs_bad_payloads_and_keeps_valid_entity():
    client = SimpleNamespace(get_entity=AsyncMock())
    dispatcher = TaskDispatcher(
        repo=None,
        queue=asyncio.Queue(),
        client=client,
    )
    tasks = [
        SimpleNamespace(id=1, task_data="{bad-json"),
        SimpleNamespace(id=2, task_data='{"chat_id": "not-an-int"}'),
        SimpleNamespace(id=3, task_data='{"peer_id": "12345"}'),
    ]

    with patch("services.task_dispatcher.logger.debug") as debug:
        await dispatcher._prefetch_entities(tasks)

    client.get_entity.assert_awaited_once_with(12345)
    assert 12345 in dispatcher._entity_cache
    assert any(
        "跳过实体预热" in str(call.args[0])
        for call in debug.call_args_list
    )


@pytest.mark.asyncio
async def test_adaptive_sleep_can_be_woken_without_waiting_full_backoff():
    dispatcher = TaskDispatcher(repo=None, queue=asyncio.Queue())
    dispatcher.current_sleep = 30.0

    sleep_task = asyncio.create_task(dispatcher._adaptive_sleep())
    await asyncio.sleep(0)

    try:
        dispatcher.wake()
        await asyncio.wait_for(sleep_task, timeout=0.1)
    finally:
        sleep_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sleep_task

    assert dispatcher.current_sleep == dispatcher.min_sleep


@pytest.mark.asyncio
async def test_adaptive_sleep_timeout_is_observable(monkeypatch, caplog):
    dispatcher = TaskDispatcher(repo=None, queue=asyncio.Queue())
    dispatcher.current_sleep = 2.0

    async def fake_wait_for(awaitable, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr("services.task_dispatcher.asyncio.wait_for", fake_wait_for)
    caplog.set_level("DEBUG", logger="services.task_dispatcher")

    await dispatcher._adaptive_sleep()

    assert "Dispatcher 空载休眠超时" in caplog.text
    assert dispatcher.current_sleep == pytest.approx(3.0)
