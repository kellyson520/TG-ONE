import asyncio
import time

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
