from unittest.mock import AsyncMock, MagicMock

import pytest

from services.cache_service import CacheService


@pytest.mark.asyncio
async def test_get_returns_none_when_cache_backend_fails(caplog):
    service = CacheService()
    cache = MagicMock()
    cache.get.side_effect = RuntimeError("direct read down")
    service._cache_map["direct_get"] = cache

    result = await service.get("key", cache_name="direct_get")

    assert result is None
    assert "Cache get failed" in caplog.text


@pytest.mark.asyncio
async def test_mutating_cache_methods_are_best_effort(caplog):
    service = CacheService()
    cache = MagicMock()
    cache.set.side_effect = RuntimeError("direct write down")
    cache.delete.side_effect = RuntimeError("direct delete down")
    cache.clear.side_effect = RuntimeError("direct clear down")
    service._cache_map["direct_mutation"] = cache

    await service.set("key", "value", ttl=60, cache_name="direct_mutation")
    await service.delete("key", cache_name="direct_mutation")
    await service.clear(cache_name="direct_mutation")

    assert "Cache set failed" in caplog.text
    assert "Cache delete failed" in caplog.text
    assert "Cache clear failed" in caplog.text


@pytest.mark.asyncio
async def test_get_or_compute_returns_factory_value_when_cache_get_fails(caplog):
    service = CacheService()
    cache = MagicMock()
    cache.get.side_effect = RuntimeError("cache read down")
    service._cache_map["failing_get"] = cache
    factory = AsyncMock(return_value="fresh")

    result = await service.get_or_compute(
        "key",
        factory,
        ttl=60,
        cache_name="failing_get",
    )

    assert result == "fresh"
    factory.assert_awaited_once()
    cache.set.assert_called_once_with("key", "fresh", 60)
    assert "Cache get failed" in caplog.text


@pytest.mark.asyncio
async def test_get_or_compute_returns_factory_value_when_cache_set_fails(caplog):
    service = CacheService()
    cache = MagicMock()
    cache.get.return_value = None
    cache.set.side_effect = RuntimeError("cache write down")
    service._cache_map["failing_set"] = cache
    factory = AsyncMock(return_value="fresh")

    result = await service.get_or_compute(
        "key",
        factory,
        ttl=60,
        cache_name="failing_set",
    )

    assert result == "fresh"
    factory.assert_awaited_once()
    assert "Cache set failed" in caplog.text
