import asyncio

import pytest

from repositories.batch_repo import AsyncBatchProcessor, BatchResult


@pytest.mark.asyncio
async def test_get_batch_from_queue_blocks_without_timeout_polling(monkeypatch):
    processor = AsyncBatchProcessor()
    original_wait_for = asyncio.wait_for

    async def fail_wait_for(awaitable, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise AssertionError(f"queue wait used polling timeout={timeout}")

    monkeypatch.setattr("repositories.batch_repo.asyncio.wait_for", fail_wait_for)

    pending_get = asyncio.create_task(processor._get_batch_from_queue())
    await asyncio.sleep(0)

    assert not pending_get.done()

    expected_batch = ["operation"]
    await processor.processing_queue.put(expected_batch)

    assert await original_wait_for(pending_get, timeout=0.1) == expected_batch


@pytest.mark.asyncio
async def test_batch_timer_waits_without_sleep_when_fully_idle(monkeypatch):
    processor = AsyncBatchProcessor(batch_timeout=0.01)
    processor.is_running = True
    original_sleep = asyncio.sleep
    sleep_calls = 0

    async def fail_sleep(delay):
        nonlocal sleep_calls
        sleep_calls += 1
        raise asyncio.CancelledError

    monkeypatch.setattr("repositories.batch_repo.asyncio.sleep", fail_sleep)

    timer_task = asyncio.create_task(processor._batch_timer())
    await original_sleep(0)

    assert sleep_calls == 0
    assert not timer_task.done()

    timer_task.cancel()
    await timer_task


@pytest.mark.asyncio
async def test_get_result_waits_on_event_without_sleep_polling(monkeypatch):
    processor = AsyncBatchProcessor()
    operation_id = "op-1"
    original_sleep = asyncio.sleep
    original_wait_for = asyncio.wait_for
    sleep_calls = 0

    async def fail_sleep(delay):
        nonlocal sleep_calls
        sleep_calls += 1
        raise AssertionError(f"get_result used polling sleep={delay}")

    monkeypatch.setattr("repositories.batch_repo.asyncio.sleep", fail_sleep)

    waiter = asyncio.create_task(processor.get_result(operation_id, timeout=1.0))
    await original_sleep(0)

    assert sleep_calls == 0
    assert not waiter.done()

    result = BatchResult(
        operation_id=operation_id,
        success=True,
        processed_count=1,
        error_count=0,
        duration=0.01,
    )
    processor.results[operation_id] = (0.0, result)
    processor._result_events[operation_id].set()

    assert await original_wait_for(waiter, timeout=0.1) is result


@pytest.mark.asyncio
async def test_batch_timer_waits_until_next_result_expiry(monkeypatch):
    processor = AsyncBatchProcessor(batch_timeout=5.0)
    processor.is_running = True
    processor.result_ttl = 300
    processor.results["fresh"] = (
        100.0,
        BatchResult(
            operation_id="fresh",
            success=True,
            processed_count=1,
            error_count=0,
            duration=0.01,
        ),
    )
    wait_timeouts = []

    async def fake_wait_for(awaitable, timeout):
        wait_timeouts.append(timeout)
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.CancelledError

    async def fake_sleep(_delay):
        raise asyncio.CancelledError

    monkeypatch.setattr("repositories.batch_repo.time.time", lambda: 100.0)
    monkeypatch.setattr("repositories.batch_repo.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr("repositories.batch_repo.asyncio.sleep", fake_sleep)

    await processor._batch_timer()

    assert wait_timeouts == [pytest.approx(300.0)]


@pytest.mark.asyncio
async def test_batch_timer_uses_first_pending_operation_deadline(monkeypatch):
    processor = AsyncBatchProcessor(batch_timeout=5.0)
    processor.is_running = True
    now = 100.0
    wait_timeouts = []

    monkeypatch.setattr("repositories.batch_repo.time.time", lambda: now)
    await processor.submit_operation("insert", "example", {"id": 1})

    now = 102.0

    async def fake_wait_for(awaitable, timeout):
        wait_timeouts.append(timeout)
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.CancelledError

    async def fake_sleep(_delay):
        raise asyncio.CancelledError

    monkeypatch.setattr("repositories.batch_repo.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr("repositories.batch_repo.asyncio.sleep", fake_sleep)

    await processor._batch_timer()

    assert wait_timeouts == [pytest.approx(3.0)]


def test_cleanup_stale_results_removes_result_at_ttl_deadline(monkeypatch):
    processor = AsyncBatchProcessor()
    processor.result_ttl = 300
    processor.results["expired"] = (
        100.0,
        BatchResult(
            operation_id="expired",
            success=True,
            processed_count=1,
            error_count=0,
            duration=0.01,
        ),
    )

    monkeypatch.setattr("repositories.batch_repo.time.time", lambda: 400.0)

    processor._cleanup_stale_results()

    assert "expired" not in processor.results
