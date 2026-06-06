from types import SimpleNamespace
from unittest.mock import MagicMock

from core.config import settings
from services import worker_service as worker_module
from services.worker_service import WorkerService


def test_worker_memory_thresholds_scale_down_on_small_vps(monkeypatch):
    monkeypatch.setattr(settings, "MEMORY_WARNING_THRESHOLD_MB", 512)
    monkeypatch.setattr(settings, "MEMORY_CRITICAL_THRESHOLD_MB", 1024)
    monkeypatch.setattr(
        worker_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=1024 * 1024 * 1024),
    )

    worker = WorkerService(
        client=MagicMock(),
        task_repo=MagicMock(),
        pipeline=MagicMock(),
    )

    assert worker.mem_warning < 512
    assert worker.mem_critical < 1024
    assert worker.mem_critical > worker.mem_warning
