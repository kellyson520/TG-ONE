import logging
import sys
from types import SimpleNamespace

from core.helpers import memory_policy


def test_resolve_process_memory_thresholds_logs_probe_failure(
    monkeypatch,
    caplog,
):
    def fail_virtual_memory():
        raise RuntimeError("memory probe unavailable")

    monkeypatch.setitem(
        sys.modules,
        "psutil",
        SimpleNamespace(virtual_memory=fail_virtual_memory),
    )
    caplog.set_level(logging.WARNING, logger=memory_policy.__name__)

    thresholds = memory_policy.resolve_process_memory_thresholds(512, 1024)

    assert thresholds == (512, 1024)
    assert "内存阈值动态计算失败" in caplog.text
    assert "memory probe unavailable" in caplog.text
