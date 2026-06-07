import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.media_service import MemoryProcessedGroupCache


@pytest.mark.asyncio
async def test_cleanup_exits_without_sleep_when_cache_empty(monkeypatch):
    cache = MemoryProcessedGroupCache()

    async def fail_sleep(delay):
        raise AssertionError(f"cleanup slept with empty cache: {delay}")

    monkeypatch.setattr("services.media_service.asyncio.sleep", fail_sleep)

    await cache._periodic_cleanup()


@pytest.mark.asyncio
async def test_cleanup_removes_expired_entries_without_sleep(monkeypatch):
    cache = MemoryProcessedGroupCache()
    cache._cache["1:10"] = 90.0

    async def fail_sleep(delay):
        raise AssertionError(f"cleanup slept before pruning expired: {delay}")

    monkeypatch.setattr("services.media_service.time.time", lambda: 100.0)
    monkeypatch.setattr("services.media_service.asyncio.sleep", fail_sleep)

    await cache._periodic_cleanup()

    assert cache._cache == {}


@pytest.mark.asyncio
async def test_cleanup_waits_until_next_expiry(monkeypatch):
    cache = MemoryProcessedGroupCache()
    cache._cache["1:10"] = 125.0
    wait_timeouts = []

    async def fake_wait_for(awaitable, timeout):
        wait_timeouts.append(timeout)
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.CancelledError

    async def fail_sleep(delay):
        raise asyncio.CancelledError

    monkeypatch.setattr("services.media_service.time.time", lambda: 100.0)
    monkeypatch.setattr("services.media_service.asyncio.wait_for", fake_wait_for)
    monkeypatch.setattr("services.media_service.asyncio.sleep", fail_sleep)

    with pytest.raises(asyncio.CancelledError):
        await cache._periodic_cleanup()

    assert wait_timeouts == [pytest.approx(25.0)]


@pytest.mark.asyncio
async def test_mark_processed_notifies_existing_cleanup_task(monkeypatch):
    cache = MemoryProcessedGroupCache()
    cleanup_event = SimpleNamespace(set=MagicMock())
    cache._cleanup_event = cleanup_event
    monkeypatch.setattr(cache, "_ensure_cleanup_task", AsyncMock())
    monkeypatch.setattr("services.media_service.time.time", lambda: 100.0)

    await cache.mark_processed(chat_id=1, group_id=10)

    cleanup_event.set.assert_called_once()


@pytest.mark.asyncio
async def test_is_processed_expires_entry_at_deadline(monkeypatch):
    cache = MemoryProcessedGroupCache()
    cache._cache["1:10"] = 100.0
    monkeypatch.setattr("services.media_service.time.time", lambda: 100.0)

    assert await cache.is_processed(chat_id=1, group_id=10) is False
    assert cache._cache == {}
