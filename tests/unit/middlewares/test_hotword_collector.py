import asyncio

import pytest

from middlewares.hotword import HotwordCollectorMiddleware


class FakeHotwordService:
    def __init__(self):
        self.processed = []

    def start_monitoring(self):
        pass

    async def stop_monitoring(self):
        pass

    async def ensure_active(self):
        pass

    async def flush_to_disk(self):
        pass

    async def process_batch(self, channel, texts):
        if channel == "bad":
            raise RuntimeError("boom")
        self.processed.append((channel, texts))


@pytest.mark.asyncio
async def test_hotword_collector_isolates_failed_channel_batches(monkeypatch):
    monkeypatch.setattr("core.config.settings.HOTWORD_BATCH_SIZE", 2)
    monkeypatch.setattr("core.config.settings.HOTWORD_SYNC_INTERVAL", 60.0)

    service = FakeHotwordService()
    collector = HotwordCollectorMiddleware(service)
    worker_task = asyncio.create_task(collector.start_worker())

    collector.queue.put_nowait(("bad", 1, "坏频道消息"))
    collector.queue.put_nowait(("good", 2, "正常频道消息"))

    for _ in range(20):
        if service.processed:
            break
        await asyncio.sleep(0.05)

    await collector.stop_worker()
    await asyncio.gather(worker_task, return_exceptions=True)

    assert service.processed
    assert service.processed[0][0] == "good"


@pytest.mark.asyncio
async def test_hotword_queue_full_log_is_rate_limited():
    collector = HotwordCollectorMiddleware(FakeHotwordService())

    assert collector._should_log_queue_full() is True
    assert collector._should_log_queue_full() is False

    collector._last_queue_full_log_at -= collector._queue_full_log_interval
    assert collector._should_log_queue_full() is True
