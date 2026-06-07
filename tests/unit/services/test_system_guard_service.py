import asyncio
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

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


@pytest.mark.asyncio
async def test_config_guard_stop_interrupts_sleep(monkeypatch):
    _patch_guard_settings(monkeypatch)
    guard = GuardService()
    original_sleep = asyncio.sleep
    release_sleep = asyncio.Event()
    sleep_calls = []

    async def blocking_sleep(delay):
        sleep_calls.append(delay)
        await release_sleep.wait()

    monkeypatch.setattr(system_module.asyncio, "sleep", blocking_sleep)

    task = asyncio.create_task(guard.start_config_guard())
    await original_sleep(0)

    guard.stop_guards()
    try:
        await asyncio.wait_for(task, timeout=0.05)
        assert sleep_calls == []
    finally:
        release_sleep.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_start_guards_async_tracks_and_reclaims_guard_tasks(monkeypatch):
    _patch_guard_settings(monkeypatch)
    guard = GuardService()
    started = []

    def make_guard(name):
        async def run():
            started.append(name)
            await guard._stop_event.wait()

        return run

    monkeypatch.setattr(guard, "start_config_guard", make_guard("config"))
    monkeypatch.setattr(guard, "start_memory_guard", make_guard("memory"))
    monkeypatch.setattr(guard, "start_db_health_guard", make_guard("db"))
    monkeypatch.setattr(guard, "start_temp_guard", make_guard("temp"))
    monkeypatch.setattr(guard, "start_file_watcher_guard", make_guard("file"))
    monkeypatch.setattr(guard, "_update_mtimes", lambda: None)

    try:
        await guard.start_guards_async()
        await asyncio.sleep(0)

        assert set(started) == {"config", "memory", "db", "temp", "file"}
        assert len(guard._guard_tasks) == 5

        await guard.stop_guards_async()

        assert guard._guard_tasks == set()
    finally:
        if hasattr(guard, "stop_guards_async"):
            await guard.stop_guards_async()
        else:
            guard._stop_event.set()
            await asyncio.sleep(0)
