import logging
from datetime import datetime

from core.helpers.search_system import SearchCache


def test_deserialize_invalid_datetime_logs_and_keeps_value(caplog):
    cache = SearchCache()
    payload = {
        "created_at": "2026-99-01T10:00:00",
        "nested": ["2026-01-02T03:04:05", "2026-13-01 00:00:00"],
    }

    with caplog.at_level(logging.WARNING, logger="core.helpers.search_system"):
        cache._deserialize_datetime_objects(payload)

    assert payload["created_at"] == "2026-99-01T10:00:00"
    assert payload["nested"][0] == datetime(2026, 1, 2, 3, 4, 5)
    assert payload["nested"][1] == "2026-13-01 00:00:00"
    assert "搜索缓存时间反序列化失败" in caplog.text
    assert "path=created_at" in caplog.text
    assert "path=nested[1]" in caplog.text
