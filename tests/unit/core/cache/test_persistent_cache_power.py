import logging

from core.cache import persistent_cache


def test_sqlite_get_miss_does_not_write_or_purge_expired_rows(
    tmp_path,
    monkeypatch,
):
    statements = []
    original_connect = persistent_cache.sqlite3.connect

    def traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(persistent_cache.sqlite3, "connect", traced_connect)
    cache = persistent_cache.SQLitePersistentCache(str(tmp_path / "cache.db"))
    statements.clear()

    assert cache.get("missing-key") is None

    write_statements = [
        statement
        for statement in statements
        if statement.strip().upper().startswith(
            ("DELETE", "INSERT", "UPDATE", "REPLACE")
        )
    ]
    assert write_statements == []


def test_sqlite_get_corrupt_expiry_degrades_to_miss_and_deletes_key(tmp_path):
    db_path = tmp_path / "cache.db"
    cache = persistent_cache.SQLitePersistentCache(str(db_path))

    conn = persistent_cache.sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO kv_cache(key, value, expires_at) VALUES (?, ?, ?)",
            ("bad-expiry", "value", "not-an-int"),
        )
        conn.commit()
    finally:
        conn.close()

    assert cache.get("bad-expiry") is None

    conn = persistent_cache.sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM kv_cache WHERE key = ?",
            ("bad-expiry",),
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == 0


def test_get_persistent_cache_logs_redis_fallback(
    tmp_path,
    monkeypatch,
    caplog,
):
    class BrokenRedisCache:
        def __init__(self, url):
            raise RuntimeError("redis unavailable")

    class FakeSQLiteCache:
        def __init__(self, db_path):
            self.db_path = db_path

    monkeypatch.setattr(persistent_cache, "_persistent_cache", None)
    monkeypatch.setattr(
        persistent_cache.settings,
        "REDIS_URL",
        "redis://unit/0",
    )
    monkeypatch.setattr(
        persistent_cache.settings,
        "PERSIST_CACHE_SQLITE",
        tmp_path / "fallback.db",
    )
    monkeypatch.setattr(
        persistent_cache,
        "RedisPersistentCache",
        BrokenRedisCache,
    )
    monkeypatch.setattr(
        persistent_cache,
        "SQLitePersistentCache",
        FakeSQLiteCache,
    )
    caplog.set_level(logging.WARNING, logger=persistent_cache.__name__)

    cache = persistent_cache.get_persistent_cache()

    assert isinstance(cache, FakeSQLiteCache)
    assert cache.db_path == str(tmp_path / "fallback.db")
    assert "Redis持久化缓存连接失败" in caplog.text
    assert "redis unavailable" in caplog.text


def test_loads_json_logs_corrupt_payload(caplog):
    caplog.set_level(logging.DEBUG, logger=persistent_cache.__name__)

    result = persistent_cache.loads_json("{not-json")

    assert result is None
    assert "缓存JSON反序列化失败" in caplog.text


def build_cache_with_failing_connection(monkeypatch):
    cache = persistent_cache.SQLitePersistentCache.__new__(
        persistent_cache.SQLitePersistentCache
    )
    cache._db_path = "broken-cache.db"

    def fail_conn():
        raise RuntimeError("sqlite unavailable")

    monkeypatch.setattr(cache, "_conn", fail_conn)
    return cache


def test_sqlite_get_connection_failure_logs_and_degrades(
    monkeypatch,
    caplog,
):
    cache = build_cache_with_failing_connection(monkeypatch)
    caplog.set_level(logging.DEBUG, logger=persistent_cache.__name__)

    assert cache.get("missing-key") is None

    assert "SQLite缓存读取连接失败" in caplog.text
    assert "missing-key" in caplog.text


def test_sqlite_set_delete_connection_failures_log_and_degrade(
    monkeypatch,
    caplog,
):
    cache = build_cache_with_failing_connection(monkeypatch)
    caplog.set_level(logging.DEBUG, logger=persistent_cache.__name__)

    cache.set("write-key", "value", ttl=30)
    cache.delete("delete-key")

    assert "SQLite缓存写入连接失败" in caplog.text
    assert "write-key" in caplog.text
    assert "SQLite缓存删除连接失败" in caplog.text
    assert "delete-key" in caplog.text
