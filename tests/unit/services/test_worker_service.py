from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from core.config import settings
from services import worker_service as worker_module
from services.worker_service import WorkerService


def test_worker_memory_thresholds_scale_down_on_small_vps(monkeypatch):
    monkeypatch.setattr(settings, "MEMORY_WARNING_THRESHOLD_MB", 512)
    monkeypatch.setattr(settings, "MEMORY_CRITICAL_THRESHOLD_MB", 1024)
    monkeypatch.setattr(
        worker_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=1024 * 1024 * 1024),
    )

    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )

    assert worker.mem_warning < 512
    assert worker.mem_critical < 1024
    assert worker.mem_critical > worker.mem_warning


async def test_retry_task_increments_attempts_on_reschedule(monkeypatch):
    monkeypatch.setattr(settings, "MAX_RETRIES", 3)

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
    monkeypatch.setattr(settings, "MAX_RETRIES", 3)

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
    monkeypatch.setattr(settings, "WORKER_MIN_CONCURRENCY", 1)

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
