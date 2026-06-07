from pathlib import Path
from types import SimpleNamespace

import psutil

from services import system_service as system_module
from services.system_service import GuardService


def _patch_guard_settings(monkeypatch, **overrides):
    values = {
        "BASE_DIR": Path("/tmp/tg-one-test"),
        "TEMP_DIR": Path("/tmp/tg-one-test/temp"),
        "TEMP_GUARD_MAX": 1024 * 1024 * 1024,
        "MEMORY_WARNING_THRESHOLD_MB": 512,
        "MEMORY_CRITICAL_THRESHOLD_MB": 1024,
    }
    values.update(overrides)
    fake_settings = SimpleNamespace(**values)
    monkeypatch.setattr(system_module, "settings", fake_settings)
    return fake_settings


def test_guard_memory_thresholds_scale_down_on_small_vps(monkeypatch):
    _patch_guard_settings(monkeypatch)
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=1024 * 1024 * 1024),
    )

    guard = GuardService()

    assert guard._memory_warning_mb < 512
    assert guard._memory_limit_mb < 1024
    assert guard._memory_limit_mb > guard._memory_warning_mb


def test_guard_memory_pressure_release_has_cooldown(monkeypatch):
    _patch_guard_settings(monkeypatch)
    guard = GuardService()

    assert guard._should_release_memory_pressure(100.0) is True

    guard._mark_memory_pressure_released(100.0)

    assert guard._should_release_memory_pressure(130.0) is False
    assert guard._should_release_memory_pressure(401.0) is True
