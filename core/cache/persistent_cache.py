"""持久化缓存：支持 Redis（优先）或本地 SQLite 文件作为后端。

用法：
    cache = get_persistent_cache()
    cache.set("key", "value", ttl=30)
    val = cache.get("key")
"""

from __future__ import annotations

import sqlite3
import threading

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

from core.helpers.json_utils import json_dumps, json_loads


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
        except Exception as exc:
            logger.debug("Redis缓存前缀删除失败 (%s): %s", prefix, exc)
            return 0

    def count_prefix(self, prefix: str) -> int:
        try:
            pattern = f"{prefix}*"
            return sum(1 for _ in self._client.scan_iter(match=pattern))
        except Exception as exc:
            logger.debug("Redis缓存前缀计数失败 (%s): %s", prefix, exc)
            return 0


class SQLitePersistentCache(BasePersistentCache):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=30)
        cur = conn.cursor()
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        return conn

    def _conn(self):
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception as e:
                logger.debug("连接健康检查失败，将重新连接: %s", e)
                try:
                    conn.close()
                except Exception as e:
                    logger.debug("关闭旧数据库连接失败: %s", e)
                self._local.conn = None

        try:
            conn = self._connect()
        except sqlite3.DatabaseError:
            if self._handle_corruption():
                conn = self._connect()
            else:
                raise
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            raise
        self._local.conn = conn
        return conn

    def _handle_corruption(self) -> bool:
        """Handle database corruption by deleting the file."""
        import os
        
        try:
            logger.error(f"❌ SQLite Cache Corruption Detected: {self._db_path}")
            if os.path.exists(self._db_path):
                # Try to backup? No, cache is disposable.
                os.remove(self._db_path)
                logger.warning(f"🧹 Corrupted cache file deleted: {self._db_path}")
            
            # Clean up SHM/WAL files if they exist
            for ext in ["-shm", "-wal"]:
                p = f"{self._db_path}{ext}"
                if os.path.exists(p):
                    os.remove(p)
            
            # Re-initialize schema
            self._ensure_schema()
            logger.info("✅ Cache database re-initialized successfully.")
            return True
        except Exception as e:
            logger.critical(f"☠️ Failed to recover from cache corruption: {e}")
            return False

    def _ensure_schema(self) -> None:
        try:
            conn = self._connect()
        except sqlite3.DatabaseError:
            # If _conn fails even after retry logic (recursive risk if not careful, but _conn handles it once)
            # Actually _conn calls _handle_corruption which calls _ensure_schema... recursion risk!
            # We need to break recursion. 
            # Simple way: _conn calls sqlite3.connect. If that fails, it's OS level.
            # If PRAGMA fails with DatabaseError, _conn calls _handle_corruption.
            # _handle_corruption deletes file and calls _ensure_schema.
            # _ensure_schema calls _conn.
            # The new file should be clean, so _conn PRAGMA should pass.
            # So recursion depth = 1. Safe.
            return

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
        except sqlite3.DatabaseError:
            conn.close()
            self._handle_corruption()
        finally:
            conn.close()

    def get(self, key: str) -> Optional[str]:
        now = int(time.time())
        try:
            conn = self._conn()
        except Exception as exc:
            logger.debug("SQLite缓存读取连接失败 (%s): %s", key, exc)
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT value, expires_at FROM kv_cache WHERE key = ?",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None

            value, expires_at = row
            try:
                is_expired = expires_at is not None and int(expires_at) < now
            except (TypeError, ValueError):
                logger.debug("SQLite缓存过期时间损坏，按miss处理: %s", key)
                is_expired = True

            if is_expired:
                cur.execute("DELETE FROM kv_cache WHERE key = ?", (key,))
                conn.commit()
                return None

            return value
        except sqlite3.DatabaseError:
            self._local.conn = None
            self._handle_corruption()
            return None

    def set(self, key: str, value: str, ttl: int) -> None:
        expires_at = int(time.time()) + max(1, int(ttl))
        try:
            conn = self._conn()
        except Exception as exc:
            logger.debug("SQLite缓存写入连接失败 (%s): %s", key, exc)
            return

        try:
            cur = conn.cursor()
            cur.execute(
                "REPLACE INTO kv_cache(key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, expires_at),
            )
            conn.commit()
        except sqlite3.DatabaseError:
            self._local.conn = None
            self._handle_corruption()

    def delete(self, key: str) -> None:
        try:
            conn = self._conn()
        except Exception as exc:
            logger.debug("SQLite缓存删除连接失败 (%s): %s", key, exc)
            return

        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM kv_cache WHERE key = ?", (key,))
            conn.commit()
        except sqlite3.DatabaseError:
            self._local.conn = None
            self._handle_corruption()

    def clear(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM kv_cache")
        conn.commit()

    def delete_prefix(self, prefix: str) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM kv_cache WHERE key LIKE ?", (prefix + "%",)
        )
        row = cur.fetchone()
        cnt = int(row[0]) if row else 0
        cur.execute("DELETE FROM kv_cache WHERE key LIKE ?", (prefix + "%",))
        conn.commit()
        return cnt

    def count_prefix(self, prefix: str) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM kv_cache WHERE key LIKE ?", (prefix + "%",)
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def stat_prefix(self, prefix: str) -> dict:
        conn = self._conn()
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


from core.config import settings

_persistent_cache: Optional[BasePersistentCache] = None


def get_persistent_cache() -> BasePersistentCache:
    global _persistent_cache
    if _persistent_cache is not None:
        return _persistent_cache
        
    url = settings.REDIS_URL
    if url:
        try:
            _persistent_cache = RedisPersistentCache(url)
            return _persistent_cache
        except Exception as e:
            # Redis 连接失败，回退到 SQLite
            logger.warning("Redis持久化缓存连接失败，回退到SQLite: %s", e)
            
    # fallback: local sqlite file
    db_path = str(settings.PERSIST_CACHE_SQLITE)
    _persistent_cache = SQLitePersistentCache(db_path)
    return _persistent_cache


def dumps_json(obj: Any) -> str:
    return json_dumps(obj)


def loads_json(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json_loads(s)
    except Exception as exc:
        logger.debug("缓存JSON反序列化失败，按miss处理: %s", exc)
        return None
