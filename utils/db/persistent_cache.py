"""持久化缓存：支持 Redis（优先）或本地 SQLite 文件作为后端。

用法：
    cache = get_persistent_cache()
    cache.set("key", "value", ttl=30)
    val = cache.get("key")
"""

from __future__ import annotations

import sqlite3

import os
import time
from typing import Any, Optional

from utils.helpers.json_utils import json_dumps, json_loads


class BasePersistentCache:
    def get(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def set(self, key: str, value: str, ttl: int) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    # 统计/管理（可选实现）
    def delete_prefix(self, prefix: str) -> int:
        """删除指定前缀的键，返回删除数量。默认不实现。"""
        raise NotImplementedError

    def count_prefix(self, prefix: str) -> int:
        """计算指定前缀键数量。默认不实现。"""
        raise NotImplementedError

    def stat_prefix(self, prefix: str) -> dict:
        """返回前缀统计信息：{'count': int, 'bytes': Optional[int]}。默认不实现。"""
        return {"count": self.count_prefix(prefix), "bytes": None}


class RedisPersistentCache(BasePersistentCache):
    def __init__(self, url: str) -> None:
        import redis  # type: ignore

        self._client = redis.from_url(url)

    def get(self, key: str) -> Optional[str]:
        val = self._client.get(key)
        return val.decode("utf-8") if val is not None else None

    def set(self, key: str, value: str, ttl: int) -> None:
        self._client.setex(key, ttl, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def clear(self) -> None:
        self._client.flushdb()

    def delete_prefix(self, prefix: str) -> int:
        try:
            count = 0
            pattern = f"{prefix}*"
            for key in self._client.scan_iter(match=pattern):
                self._client.delete(key)
                count += 1
            return count
        except Exception:
            return 0

    def count_prefix(self, prefix: str) -> int:
        try:
            pattern = f"{prefix}*"
            return sum(1 for _ in self._client.scan_iter(match=pattern))
        except Exception:
            return 0


class SQLitePersistentCache(BasePersistentCache):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def _conn(self):
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA busy_timeout=30000")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        return conn

    def _ensure_schema(self) -> None:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at INTEGER
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_expires ON kv_cache(expires_at)"
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Optional[str]:
        now = int(time.time())
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM kv_cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            conn.commit()
            cur.execute("SELECT value FROM kv_cache WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def set(self, key: str, value: str, ttl: int) -> None:
        expires_at = int(time.time()) + max(1, int(ttl))
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "REPLACE INTO kv_cache(key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, expires_at),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, key: str) -> None:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM kv_cache WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()

    def clear(self) -> None:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM kv_cache")
            conn.commit()
        finally:
            conn.close()

    def delete_prefix(self, prefix: str) -> int:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM kv_cache WHERE key LIKE ?", (prefix + "%",)
            )
            row = cur.fetchone()
            cnt = int(row[0]) if row else 0
            cur.execute("DELETE FROM kv_cache WHERE key LIKE ?", (prefix + "%",))
            conn.commit()
            return cnt
        finally:
            conn.close()

    def count_prefix(self, prefix: str) -> int:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM kv_cache WHERE key LIKE ?", (prefix + "%",)
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def stat_prefix(self, prefix: str) -> dict:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*), SUM(LENGTH(value)) FROM kv_cache WHERE key LIKE ?",
                (prefix + "%",),
            )
            row = cur.fetchone()
            return {
                "count": int(row[0]) if row and row[0] is not None else 0,
                "bytes": int(row[1]) if row and row[1] is not None else 0,
            }
        finally:
            conn.close()


_persistent_cache: Optional[BasePersistentCache] = None


def get_persistent_cache() -> BasePersistentCache:
    global _persistent_cache
    if _persistent_cache is not None:
        return _persistent_cache
    url = os.getenv("REDIS_URL") or os.getenv("REDIS_CONNECTION_URL")
    if url:
        try:
            _persistent_cache = RedisPersistentCache(url)
            return _persistent_cache
        except Exception:
            pass
    # fallback: local sqlite file
    db_path = os.getenv("PERSIST_CACHE_SQLITE", os.path.join(os.getcwd(), "cache.db"))
    _persistent_cache = SQLitePersistentCache(db_path)
    return _persistent_cache


def dumps_json(obj: Any) -> str:
    return json_dumps(obj)


def loads_json(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json_loads(s)
    except Exception:
        return None
