"""SQLitePersistentCache 测试 — TTL 驱逐 + CRUD + 前缀操作 + 线程安全"""
import pytest
import time
import tempfile
import threading
from core.cache.persistent_cache import SQLitePersistentCache


@pytest.fixture
def cache(tmp_path):
    """每个测试用例独立的 SQLite 缓存"""
    db_path = str(tmp_path / "test_cache.db")
    return SQLitePersistentCache(db_path)


class TestBasicCRUD:
    """基本增删改查"""

    def test_set_and_get(self, cache):
        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self, cache):
        assert cache.get("missing") is None

    def test_set_overwrite(self, cache):
        cache.set("key1", "old", ttl=60)
        cache.set("key1", "new", ttl=60)
        assert cache.get("key1") == "new"

    def test_delete(self, cache):
        cache.set("key1", "value1", ttl=60)
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache):
        cache.delete("missing")  # 不应抛异常

    def test_clear(self, cache):
        cache.set("a", "1", ttl=60)
        cache.set("b", "2", ttl=60)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None


class TestTTLEviction:
    """TTL 过期驱逐测试 — #4 的核心修复"""

    def test_expired_key_returns_none(self, cache):
        """TTL=2 秒后过期（sleep 3s 确保 int(time) 越过边界）"""
        cache.set("expire_me", "data", ttl=2)
        assert cache.get("expire_me") == "data"
        time.sleep(3)
        assert cache.get("expire_me") is None

    def test_not_expired_key_persists(self, cache):
        """TTL=30 秒不应过期"""
        cache.set("stay", "data", ttl=30)
        assert cache.get("stay") == "data"

    def test_ttl_boundary(self, cache):
        """TTL=2 秒边界：1秒时还在，3秒时过期"""
        cache.set("boundary", "val", ttl=2)
        time.sleep(1)
        assert cache.get("boundary") == "val"
        time.sleep(2.5)
        assert cache.get("boundary") is None

    def test_zero_ttl_clamped_to_1(self, cache):
        """TTL=0 应被钳制为 1 秒（max(1, ttl)）"""
        cache.set("zero_ttl", "val", ttl=0)
        assert cache.get("zero_ttl") == "val"

    def test_expired_key_deleted_from_db(self, cache):
        """过期后应从数据库中删除"""
        cache.set("to_delete", "val", ttl=2)
        time.sleep(3)
        cache.get("to_delete")  # 触发删除
        assert cache.get("to_delete") is None

    def test_multiple_keys_mixed_expiry(self, cache):
        """多个 key，部分过期部分存活"""
        cache.set("expire", "old", ttl=2)
        cache.set("alive", "new", ttl=60)
        time.sleep(3)
        assert cache.get("expire") is None
        assert cache.get("alive") == "new"


class TestPrefixOperations:
    """前缀操作测试"""

    def test_delete_prefix(self, cache):
        cache.set("user:1", "alice", ttl=60)
        cache.set("user:2", "bob", ttl=60)
        cache.set("other:1", "charlie", ttl=60)
        count = cache.delete_prefix("user:")
        assert count == 2
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("other:1") == "charlie"

    def test_count_prefix(self, cache):
        cache.set("a:1", "x", ttl=60)
        cache.set("a:2", "y", ttl=60)
        cache.set("b:1", "z", ttl=60)
        assert cache.count_prefix("a:") == 2
        assert cache.count_prefix("b:") == 1
        assert cache.count_prefix("c:") == 0

    def test_stat_prefix(self, cache):
        cache.set("s:1", "hello", ttl=60)
        cache.set("s:2", "world", ttl=60)
        stats = cache.stat_prefix("s:")
        assert stats["count"] == 2
        assert stats["bytes"] == len("hello") + len("world")

    def test_stat_prefix_empty(self, cache):
        stats = cache.stat_prefix("empty:")
        assert stats["count"] == 0
        assert stats["bytes"] == 0


class TestThreadSafety:
    """线程安全测试 — threading.local() 连接复用"""

    def test_concurrent_writes(self, cache):
        """多线程并发写入"""
        errors = []

        def writer(thread_id):
            try:
                for i in range(10):
                    cache.set(f"t{thread_id}:{i}", f"val{i}", ttl=60)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.count_prefix("t0:") == 10
        assert cache.count_prefix("t4:") == 10

    def test_concurrent_reads_and_writes(self, cache):
        """多线程并发读写"""
        cache.set("shared", "data", ttl=60)
        errors = []

        def reader():
            try:
                for _ in range(20):
                    val = cache.get("shared")
                    assert val in ("data", None)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(20):
                    cache.set(f"new:{i}", f"v{i}", ttl=60)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
