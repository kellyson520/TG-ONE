from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import psutil

from core.exceptions import TransientError
from services import worker_service as worker_module
from services.worker_service import WorkerService


def _patch_worker_settings(monkeypatch, **overrides):
    values = {
        "MEMORY_WARNING_THRESHOLD_MB": 512,
        "MEMORY_CRITICAL_THRESHOLD_MB": 1024,
        "WORKER_QUEUE_SIZE": 10,
        "WORKER_MIN_CONCURRENCY": 1,
        "WORKER_MAX_CONCURRENCY": 4,
        "MAX_RETRIES": 3,
        "RETRY_BASE_DELAY": 1,
        "RETRY_BACKOFF_FACTOR": 2,
        "RETRY_MAX_DELAY": 60,
    }
    values.update(overrides)
    fake_settings = SimpleNamespace(**values)
    monkeypatch.setattr(worker_module, "settings", fake_settings)
    return fake_settings


def test_worker_memory_thresholds_scale_down_on_small_vps(monkeypatch):
    _patch_worker_settings(
        monkeypatch,
        MEMORY_WARNING_THRESHOLD_MB=512,
        MEMORY_CRITICAL_THRESHOLD_MB=1024,
    )
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(total=1024 * 1024 * 1024))

    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )

    assert worker.mem_warning < 512
    assert worker.mem_critical < 1024
    assert worker.mem_critical > worker.mem_warning


async def test_retry_task_increments_attempts_on_reschedule(monkeypatch):
    _patch_worker_settings(monkeypatch, MAX_RETRIES=3)

    repo = SimpleNamespace(reschedule=AsyncMock(), fail=AsyncMock())
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
    )
    task = SimpleNamespace(id=10, attempts=0)

    await worker._retry_task(task, RuntimeError("temporary"), MagicMock())

    repo.reschedule.assert_awaited_once()
    assert repo.reschedule.await_args.kwargs["increment_attempts"] is True
    repo.fail.assert_not_awaited()


async def test_retry_task_fails_after_max_retries(monkeypatch):
    _patch_worker_settings(monkeypatch, MAX_RETRIES=3)

    repo = SimpleNamespace(reschedule=AsyncMock(), fail=AsyncMock())
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
    )
    task = SimpleNamespace(id=11, attempts=3)

    await worker._retry_task(task, RuntimeError("still failing"), MagicMock())

    repo.fail.assert_awaited_once()
    repo.reschedule.assert_not_awaited()


async def test_invalid_task_json_fails_locked_group_tasks():
    repo = SimpleNamespace(fail=AsyncMock())
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
    )
    main_task = SimpleNamespace(id=1, task_data="{bad-json", task_type="process_message")
    group_task = SimpleNamespace(id=2, task_data="{}", task_type="process_message")

    await worker._process_task_safely(main_task, MagicMock(), group_tasks=[group_task])

    assert [call.args[0] for call in repo.fail.await_args_list] == [1, 2]


async def test_scale_down_queues_idle_shutdown_without_cancelling_worker(monkeypatch):
    _patch_worker_settings(monkeypatch, WORKER_MIN_CONCURRENCY=1)

    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )
    fake_task = MagicMock()
    worker.workers = {fake_task: "worker-1", MagicMock(): "worker-2"}

    await worker._kill_worker()

    fake_task.cancel.assert_not_called()
    assert worker._scale_down_requests == 1
    assert await worker.task_queue.get() is None


async def test_ensure_connected_raises_transient_when_reconnect_fails(monkeypatch):
    client = MagicMock()
    client.is_connected.return_value = False
    client.connect = AsyncMock(side_effect=ConnectionError("network down"))
    worker = WorkerService(
        client=client,
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )
    monkeypatch.setattr(worker_module.asyncio, "sleep", AsyncMock())

    try:
        await worker._ensure_connected()
    except TransientError as exc:
        assert "reconnect failed" in str(exc)
    else:
        raise AssertionError("_ensure_connected should raise TransientError")


async def test_worker_loop_retries_group_when_connection_guard_fails(monkeypatch):
    _patch_worker_settings(monkeypatch, MAX_RETRIES=3)
    monkeypatch.setattr(worker_module.asyncio, "sleep", AsyncMock())

    repo = SimpleNamespace(reschedule=AsyncMock(), fail=AsyncMock(), complete=AsyncMock())
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
    )
    worker.running = True
    monkeypatch.setattr(
        worker,
        "_ensure_connected",
        AsyncMock(side_effect=TransientError("client disconnected")),
    )

    task = SimpleNamespace(
        id=21,
        attempts=0,
        grouped_id=None,
        task_type="process_message",
        task_data='{"chat_id": 100, "message_id": 200}',
    )
    await worker.task_queue.put(task)
    await worker.task_queue.put(None)

    await worker._worker_loop("worker-test")

    repo.reschedule.assert_awaited_once()
    repo.fail.assert_not_awaited()
    repo.complete.assert_not_awaited()


async def test_connection_backoff_does_not_consume_task_attempt(monkeypatch):
    _patch_worker_settings(monkeypatch, MAX_RETRIES=3)

    repo = SimpleNamespace(reschedule=AsyncMock(), fail=AsyncMock())
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
    )
    task = SimpleNamespace(id=31, attempts=3)
    error = TransientError(
        "client reconnect cooling down",
        context={"retry_delay_seconds": 5.0, "increment_attempts": False},
    )
    before = datetime.utcnow()

    await worker._retry_task(task, error, MagicMock())

    repo.fail.assert_not_awaited()
    repo.reschedule.assert_awaited_once()
    assert repo.reschedule.await_args.args[0] == 31
    assert before + timedelta(seconds=4.5) <= repo.reschedule.await_args.args[1]
    assert repo.reschedule.await_args.kwargs["increment_attempts"] is False
