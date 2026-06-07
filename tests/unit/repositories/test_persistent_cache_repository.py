import logging
from unittest.mock import MagicMock

import pytest

from repositories import persistent_cache_repository as repo_module


@pytest.mark.asyncio
async def test_get_reads_from_underlying_persistent_cache(monkeypatch):
    cache = MagicMock()
    cache.get.return_value = "1"
    monkeypatch.setattr(
        repo_module,
        "get_persistent_cache",
        lambda: cache,
        raising=False,
    )

    repo = repo_module.PersistentCacheRepository()

    result = await repo.get("sig:123:abc")

    assert result == "1"
    cache.get.assert_called_once_with("sig:123:abc")


@pytest.mark.asyncio
async def test_set_writes_to_persistent_cache_with_expire(monkeypatch):
    cache = MagicMock()
    monkeypatch.setattr(
        repo_module,
        "get_persistent_cache",
        lambda: cache,
        raising=False,
    )

    repo = repo_module.PersistentCacheRepository()

    result = await repo.set("vhash:file-1", "hash-value", expire=42)

    assert result is True
    cache.set.assert_called_once_with("vhash:file-1", "hash-value", ttl=42)


@pytest.mark.asyncio
async def test_get_failure_degrades_to_miss_and_logs(monkeypatch, caplog):
    cache = MagicMock()
    cache.get.side_effect = RuntimeError("cache unavailable")
    monkeypatch.setattr(
        repo_module,
        "get_persistent_cache",
        lambda: cache,
        raising=False,
    )
    caplog.set_level(logging.DEBUG, logger=repo_module.__name__)

    repo = repo_module.PersistentCacheRepository()

    result = await repo.get("hash:123:bad")

    assert result is None
    assert "PCache读取失败" in caplog.text
    assert "hash:123:bad" in caplog.text
