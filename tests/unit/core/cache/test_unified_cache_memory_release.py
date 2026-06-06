from core.cache import unified_cache


def test_release_memory_caches_is_noop_before_initialization(monkeypatch):
    monkeypatch.setattr(unified_cache, "smart_cache", None)

    result = unified_cache.release_memory_caches()

    assert result == {
        "total_caches": 0,
        "caches_cleared": [],
        "entries_cleared": 0,
        "access_patterns_cleared": 0,
    }
    assert unified_cache.smart_cache is None


def test_release_memory_caches_clears_l1_only(monkeypatch):
    monkeypatch.setattr(unified_cache, "smart_cache", None)
    cache = unified_cache.get_smart_cache("unit_release", enable_persistent=False)
    cache.set("a", {"value": 1})
    cache.set("b", {"value": 2})

    result = unified_cache.release_memory_caches()

    assert result["total_caches"] == 1
    assert result["caches_cleared"] == ["unit_release"]
    assert result["entries_cleared"] == 2
    assert cache.get_stats().size == 0
    assert cache.get("a") is None
