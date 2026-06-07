import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.db_buffer import GroupCommitCoordinator


@pytest.mark.asyncio
async def test_group_commit_idle_wait_has_no_timeout(monkeypatch):
    timeout_waits = 0

    async def fake_wait_for(awaitable, timeout):
        nonlocal timeout_waits
        timeout_waits += 1
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.CancelledError

    monkeypatch.setattr("services.db_buffer.asyncio.wait_for", fake_wait_for)

    coordinator = GroupCommitCoordinator(lambda: None)
    await coordinator.start()
    await asyncio.sleep(0)

    assert timeout_waits == 0

    await coordinator.stop()


@pytest.mark.asyncio
async def test_group_commit_time_flushes_pending_item_without_stop():
    session = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_factory = MagicMock(return_value=session_cm)

    coordinator = GroupCommitCoordinator(session_factory)
    coordinator.buffer._flush_interval = 0.01

    await coordinator.start()
    await coordinator.buffer.add(MagicMock())
    await asyncio.sleep(0.05)

    assert session.add_all.called
    assert session.commit.await_count == 1

    await coordinator.stop()


@pytest.mark.asyncio
async def test_group_commit_deadline_timeout_is_observable(caplog):
    coordinator = GroupCommitCoordinator(lambda: None)
    coordinator.buffer._flush_interval = 0.01
    await coordinator.buffer.add(MagicMock())

    caplog.set_level("DEBUG", logger="services.db_buffer")

    await coordinator._wait_for_work_or_deadline()

    assert "GroupCommitCoordinator等待超时" in caplog.text
    assert "buffer_size=1" in caplog.text
