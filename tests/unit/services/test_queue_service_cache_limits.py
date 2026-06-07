import asyncio
import time

import pytest

from core.exceptions import TransientError
from services.network.circuit_breaker import CircuitState
from services.queue_service import MessageQueueService, TelegramQueueService


def test_target_semaphore_cache_evicts_idle_entries():
    service = TelegramQueueService()
    service._semaphore_cache_max = 3

    for i in range(10):
        service._get_target_sem(str(i))

    assert len(service._target_semaphores) <= 3


async def test_target_semaphore_cache_keeps_active_entries():
    service = TelegramQueueService()
    service._semaphore_cache_max = 1

    active = service._get_target_sem("active")
    await active.acquire()
    try:
        for i in range(5):
            service._get_target_sem(f"idle-{i}")

        assert "active" in service._target_semaphores
    finally:
        active.release()


def test_flood_wait_cache_prunes_expired_and_caps_size():
    service = TelegramQueueService()
    service._flood_wait_cache_max = 3
    service._flood_wait_until.clear()
    service._flood_wait_until["expired"] = time.time() - 1

    for i in range(10):
        service._handle_flood_wait(str(i), f"src->{i}", 30)

    assert "expired" not in service._flood_wait_until
    assert len(service._flood_wait_until) <= 3


def test_forward_pacing_uses_configured_intervals(monkeypatch):
    service = TelegramQueueService()
    monkeypatch.setattr("services.queue_service.time.time", lambda: 1000.0)
    monkeypatch.setattr("services.queue_service.settings.FORWARD_GLOBAL_MIN_INTERVAL_MS", 150)
    monkeypatch.setattr("services.queue_service.settings.FORWARD_TARGET_MIN_INTERVAL_MS", 1200)
    monkeypatch.setattr("services.queue_service.settings.FORWARD_PAIR_MIN_INTERVAL_MS", 800)
    monkeypatch.setattr("services.queue_service.settings.FORWARD_PACING_JITTER", 0.0)

    service._update_next_at("target", "source->target")

    assert service._global_next_at == pytest.approx(1000.150)
    assert service._target_next_at["target"] == pytest.approx(1001.200)
    assert service._pair_next_at["source->target"] == pytest.approx(1000.800)


async def test_message_queue_processes_falsy_items():
    service = MessageQueueService(max_size=10, workers=1)
    processed = []

    async def processor(batch):
        processed.extend(batch)

    async def wait_until_processed():
        while not processed:
            await asyncio.sleep(0.01)

    service.set_processor(processor)
    await service.start()
    try:
        await service.enqueue(0)
        await asyncio.wait_for(wait_until_processed(), timeout=1.0)
        assert processed == [0]
    finally:
        if processed:
            await service.stop()
        else:
            for task in service._worker_tasks:
                task.cancel()
            await asyncio.gather(*service._worker_tasks, return_exceptions=True)


async def test_message_queue_retries_batch_after_processor_failure():
    service = MessageQueueService(max_size=10, workers=1)
    item = ("persist", {"chat_id": 42}, 50)
    attempts = 0
    processed = []

    async def processor(batch):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary db failure")
        processed.extend(batch)

    async def wait_until_processed():
        while not processed:
            await asyncio.sleep(0.01)

    service.set_processor(processor)
    await service.start()
    try:
        await service.enqueue(item)
        await asyncio.wait_for(wait_until_processed(), timeout=2.0)

        assert attempts >= 2
        assert processed == [item]
    finally:
        if processed:
            await service.stop()
        else:
            for task in service._worker_tasks:
                task.cancel()
            await asyncio.gather(*service._worker_tasks, return_exceptions=True)


async def test_short_flood_wait_does_not_hold_global_semaphore():
    service = TelegramQueueService()
    service._global_sem = asyncio.Semaphore(1)
    service._flood_wait_until.clear()
    service._flood_wait_until["blocked"] = time.time() + 0.2

    async def blocked_operation():
        return "blocked"

    blocked_task = asyncio.create_task(
        service.run_guarded_operation("blocked", None, "BlockedTarget", blocked_operation)
    )

    try:
        await asyncio.sleep(0.02)

        async def free_operation():
            return "free"

        result = await asyncio.wait_for(
            service.run_guarded_operation("free", None, "FreeTarget", free_operation),
            timeout=0.08,
        )

        assert result == "free"
        assert await asyncio.wait_for(blocked_task, timeout=0.5) == "blocked"
    finally:
        if not blocked_task.done():
            blocked_task.cancel()
            await asyncio.gather(blocked_task, return_exceptions=True)


async def test_terminal_telegram_errors_do_not_open_global_circuit():
    from telethon.errors import MessageIdInvalidError

    service = TelegramQueueService()
    service._telegram_breaker.failure_threshold = 2

    async def terminal_operation():
        raise MessageIdInvalidError(request=None)

    for _ in range(3):
        with pytest.raises(MessageIdInvalidError):
            await service.run_guarded_operation(
                "target",
                "source",
                "ForwardTerminal",
                terminal_operation,
                handle_flood_wait_sleep=False,
            )

    assert service._telegram_breaker.state is CircuitState.CLOSED
    assert service._telegram_breaker.failure_count == 0


async def test_open_telegram_circuit_raises_transient_without_attempt_increment():
    service = TelegramQueueService()
    service._telegram_breaker.state = CircuitState.OPEN
    service._telegram_breaker.last_failure_time = time.time()

    async def operation():
        raise AssertionError("operation should not run while circuit is open")

    with pytest.raises(TransientError) as exc_info:
        await service.run_guarded_operation("target", None, "GetMsgs", operation)

    assert exc_info.value.context["increment_attempts"] is False
    assert exc_info.value.context["retry_delay_seconds"] == service._telegram_breaker.recovery_timeout
