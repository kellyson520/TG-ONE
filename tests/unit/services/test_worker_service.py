from datetime import datetime, timedelta
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import asyncio
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


def test_get_performance_stats_logs_memory_probe_failure(monkeypatch, caplog):
    _patch_worker_settings(monkeypatch)

    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )
    worker.workers = {}

    def fail_process():
        raise RuntimeError("process probe unavailable")

    monkeypatch.setattr(psutil, "Process", fail_process)
    caplog.set_level(logging.WARNING, logger=worker_module.__name__)

    stats = worker.get_performance_stats()

    assert stats["current_workers"] == 0
    assert "memory" not in stats
    assert "Worker memory stats unavailable" in caplog.text
    assert "process probe unavailable" in caplog.text


def test_probe_scaling_resources_logs_process_probe_failure(monkeypatch, caplog):
    _patch_worker_settings(monkeypatch)
    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )

    def fail_process():
        raise RuntimeError("process probe unavailable")

    monkeypatch.setattr(worker_module.psutil, "cpu_percent", lambda interval=None: 25.0)
    monkeypatch.setattr(worker_module.psutil, "Process", fail_process)
    caplog.set_level(logging.WARNING, logger=worker_module.__name__)

    assert worker._probe_scaling_resources() == (0, 0, 0)
    assert "Worker resource probe unavailable" in caplog.text
    assert "process probe unavailable" in caplog.text


def test_probe_scaling_resources_logs_loadavg_failure(monkeypatch, caplog):
    _patch_worker_settings(monkeypatch)
    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )
    process = MagicMock()
    process.memory_info.return_value = SimpleNamespace(rss=256 * 1024 * 1024)

    def fail_loadavg():
        raise AttributeError("load average unavailable")

    monkeypatch.setattr(worker_module.psutil, "cpu_percent", lambda interval=None: 12.5)
    monkeypatch.setattr(worker_module.psutil, "Process", lambda: process)
    monkeypatch.setattr(worker_module.psutil, "getloadavg", fail_loadavg)
    caplog.set_level(logging.DEBUG, logger=worker_module.__name__)

    assert worker._probe_scaling_resources() == (12.5, 256.0, 0)
    assert "Worker load average unavailable" in caplog.text
    assert "load average unavailable" in caplog.text


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


async def test_worker_loop_wakes_dispatcher_after_queue_slot_frees(monkeypatch):
    _patch_worker_settings(monkeypatch)

    dispatcher = SimpleNamespace(wake=MagicMock())
    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )
    worker.dispatcher = dispatcher
    worker.running = True

    await worker.task_queue.put(None)

    await worker._worker_loop("worker-test")

    dispatcher.wake.assert_called_once()


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


async def test_manual_download_forward_transient_error_retries_task(monkeypatch):
    _patch_worker_settings(monkeypatch, MAX_RETRIES=3)
    import core.helpers.id_utils as id_utils

    repo = SimpleNamespace(reschedule=AsyncMock(), fail=AsyncMock(), complete=AsyncMock())
    downloader = SimpleNamespace(push_to_queue=AsyncMock(return_value="/tmp/manual.bin"))
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
        downloader=downloader,
    )
    message = SimpleNamespace(id=200, text="caption")
    task = SimpleNamespace(
        id=41,
        attempts=0,
        task_type="manual_download",
        task_data='{"chat_id": 100, "message_id": 200, "target_chat_id": 300}',
    )
    monkeypatch.setattr(id_utils, "get_display_name_async", AsyncMock(return_value="source"))
    monkeypatch.setattr(worker_module, "get_messages_queued", AsyncMock(return_value=message))
    monkeypatch.setattr(
        worker_module,
        "send_file_queued",
        AsyncMock(side_effect=TransientError("temporary send failure")),
    )

    await worker._process_task_safely(task, MagicMock())

    repo.reschedule.assert_awaited_once()
    repo.complete.assert_not_awaited()
    repo.fail.assert_not_awaited()


async def test_start_waits_for_stop_without_keepalive_sleep(monkeypatch):
    _patch_worker_settings(
        monkeypatch,
        WORKER_MIN_CONCURRENCY=0,
        WORKER_MAX_CONCURRENCY=1,
    )
    import services.task_dispatcher as dispatcher_module

    dispatcher = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        wake=MagicMock(),
    )
    repo = SimpleNamespace(rescue_stuck_tasks=AsyncMock(return_value=0))
    worker = WorkerService(
        client=MagicMock(),
        task_repo=repo,
        pipeline=MagicMock(),
    )
    monkeypatch.setattr(
        dispatcher_module,
        "TaskDispatcher",
        lambda _repo, _queue: dispatcher,
    )
    monkeypatch.setattr(worker, "_monitor_scaling", AsyncMock())
    monkeypatch.setattr(worker, "_monitor_loop_lag", AsyncMock())

    original_sleep = asyncio.sleep
    original_wait_for = asyncio.wait_for
    sleep_released = asyncio.Event()
    sleep_calls = 0

    async def fake_sleep(_delay):
        nonlocal sleep_calls
        sleep_calls += 1
        await sleep_released.wait()

    monkeypatch.setattr(worker_module.asyncio, "sleep", fake_sleep)

    start_task = asyncio.create_task(worker.start())
    try:
        await original_sleep(0)

        assert sleep_calls == 0
        assert not start_task.done()

        await worker.stop()
        assert await original_wait_for(start_task, timeout=0.1) is None
    finally:
        sleep_released.set()
        if not start_task.done():
            start_task.cancel()
            await asyncio.gather(start_task, return_exceptions=True)
