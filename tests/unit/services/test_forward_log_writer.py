import asyncio
from unittest.mock import AsyncMock

import pytest

from services.forward_log_writer import ForwardLogBatchWriter, ForwardLogEntry


@pytest.mark.asyncio
async def test_start_does_not_create_idle_flush_task():
    writer = ForwardLogBatchWriter()

    await writer.start()
    try:
        assert writer._running is True
        assert writer._flush_task is None
    finally:
        await writer.stop()


@pytest.mark.asyncio
async def test_delayed_flush_task_exits_after_queue_drains():
    writer = ForwardLogBatchWriter()
    writer.FLUSH_INTERVAL = 0.01
    writer._batch_insert = AsyncMock(return_value=True)

    await writer.start()
    await writer.log(
        ForwardLogEntry(
            rule_id=1,
            source_chat_id="1",
            target_chat_id="2",
            source_message_id=1,
        )
    )

    await asyncio.wait_for(writer._flush_task, timeout=1.0)

    assert writer._flush_task is None
    assert len(writer._queue) == 0
    assert writer._stats["total_written"] == 1
    await writer.stop()


@pytest.mark.asyncio
async def test_threshold_flush_is_single_flight():
    writer = ForwardLogBatchWriter()
    writer.BATCH_SIZE = 3
    release_flush = asyncio.Event()

    async def slow_flush():
        await release_flush.wait()

    writer._flush = AsyncMock(side_effect=slow_flush)

    for i in range(10):
        await writer.log(
            ForwardLogEntry(
                rule_id=1,
                source_chat_id="1",
                target_chat_id="2",
                source_message_id=i,
            )
        )

    await asyncio.sleep(0)
    assert writer._flush.await_count == 1
    release_flush.set()
    await asyncio.wait_for(writer._flush_trigger_task, timeout=1.0)
