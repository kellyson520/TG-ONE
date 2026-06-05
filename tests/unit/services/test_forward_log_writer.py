import asyncio
from unittest.mock import AsyncMock

import pytest

from services.forward_log_writer import ForwardLogBatchWriter, ForwardLogEntry


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
