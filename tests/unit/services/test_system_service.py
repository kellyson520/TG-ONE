import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.system_service import SystemService


class OneShot:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_get_system_status_logs_worker_stats_failure():
    process = MagicMock()
    process.oneshot.return_value = OneShot()
    process.cpu_percent.return_value = 12.5
    process.memory_info.return_value = SimpleNamespace(rss=128 * 1024 * 1024)
    process.create_time.return_value = time.time() - 120
    process.memory_percent.return_value = 4.2

    worker = MagicMock()
    worker.get_performance_stats.side_effect = RuntimeError("worker offline")
    container = SimpleNamespace(worker=worker)
    update_service = SimpleNamespace(
        get_current_version=AsyncMock(return_value=None),
        _is_git_repo=True,
    )

    with (
        patch("psutil.Process", return_value=process),
        patch(
            "psutil.disk_usage",
            return_value=SimpleNamespace(percent=9.5),
        ),
        patch("version.get_version", return_value="test-version"),
        patch("services.update_service.update_service", update_service),
        patch("services.system_service.logger.warning") as warning,
    ):
        svc = SystemService()
        svc.set_worker(worker)
        status = await svc.get_system_status()

    assert status["worker"] == {}
    assert any(
        "获取 Worker 性能统计失败" in str(call.args[0])
        for call in warning.call_args_list
    )
