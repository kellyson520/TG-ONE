import logging

from services.dedup import engine as engine_module


def test_lsh_forest_creation_failure_logs_and_degrades(monkeypatch, caplog):
    import core.algorithms.lsh_forest as lsh_module

    class BrokenLSHForest:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("lsh unavailable")

    monkeypatch.setattr(lsh_module, "LSHForest", BrokenLSHForest)
    dedup = engine_module.SmartDeduplicator.__new__(
        engine_module.SmartDeduplicator
    )
    dedup.lsh_forests = {}
    caplog.set_level(logging.WARNING, logger=engine_module.__name__)

    forest = dedup._get_lsh_forest("chat-1")

    assert forest is None
    assert dedup.lsh_forests == {}
    assert "LSH Forest初始化失败" in caplog.text
    assert "chat-1" in caplog.text
    assert "lsh unavailable" in caplog.text
