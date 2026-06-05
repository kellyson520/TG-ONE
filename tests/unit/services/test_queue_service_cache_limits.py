import asyncio
import time

from services.queue_service import TelegramQueueService


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
