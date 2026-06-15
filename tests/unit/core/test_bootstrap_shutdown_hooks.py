import logging
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services import system_service as system_module
from core.bootstrap import Bootstrap


class _ImportBlocker(types.ModuleType):
    """Module proxy that raises ImportError on any public attribute access.

    Used to simulate missing optional modules in tests without
    monkeypatching builtins.__import__.
    """

    def __init__(self, name: str, error_msg: str = ""):
        super().__init__(name)
        self.__dict__["_error_msg"] = error_msg
        self.__path__ = []  # mark as a package to prevent sub-module lookup

    def __getattr__(self, attr: str):
        if attr.startswith("_") and attr != "__path__":
            raise AttributeError(attr)
        raise ImportError(self._error_msg)


class FakeShutdownCoordinator:
    def __init__(self):
        self.cleanups = []

    def register_cleanup(self, callback, priority, timeout, name=None):
        self.cleanups.append({
            "callback": callback,
            "priority": priority,
            "timeout": timeout,
            "name": name,
        })


def test_register_shutdown_hooks_logs_missing_web_stop_hook(
    monkeypatch,
    caplog,
):
    bootstrap = Bootstrap.__new__(Bootstrap)
    bootstrap.user_client = None
    bootstrap.bot_client = None
    bootstrap.coordinator = FakeShutdownCoordinator()

    # Simulate missing web_admin module via sys.modules instead of
    # monkeypatching builtins.__import__.
    blocker = _ImportBlocker("web_admin.fastapi_app", "web admin unavailable")
    monkeypatch.setitem(sys.modules, "web_admin.fastapi_app", blocker)
    monkeypatch.setitem(
        sys.modules,
        "web_admin",
        _ImportBlocker("web_admin", "web admin unavailable"),
    )

    monkeypatch.setattr("core.bootstrap.settings.WEB_ENABLED", True)
    caplog.set_level(logging.DEBUG, logger="core.bootstrap")

    bootstrap._register_shutdown_hooks()

    assert "Web 管理服务停止钩子不可用" in caplog.text
    assert "web admin unavailable" in caplog.text
    assert all(
        cleanup["name"] != "web_server_stop"
        for cleanup in bootstrap.coordinator.cleanups
    )


@pytest.mark.asyncio
async def test_auxiliary_shutdown_waits_for_guard_tasks(monkeypatch):
    bootstrap = Bootstrap.__new__(Bootstrap)
    bootstrap.user_client = None
    bootstrap.bot_client = None
    bootstrap.coordinator = FakeShutdownCoordinator()
    guard = SimpleNamespace(
        stop_guards=MagicMock(),
        stop_guards_async=AsyncMock(),
    )
    cron = SimpleNamespace(stop=AsyncMock())
    update = SimpleNamespace(stop=MagicMock())
    sleep_manager = SimpleNamespace(stop=MagicMock())
    task_status_sink = SimpleNamespace(stop=AsyncMock())

    import scheduler.cron_service as cron_module
    import services.update_service as update_module
    import core.helpers.sleep_manager as sleep_module

    monkeypatch.setattr("core.bootstrap.settings.WEB_ENABLED", False)
    monkeypatch.setattr(cron_module, "cron_service", cron)
    monkeypatch.setattr(system_module, "guard_service", guard)
    monkeypatch.setattr(update_module, "update_service", update)
    monkeypatch.setattr(sleep_module, "sleep_manager", sleep_manager)
    monkeypatch.setattr("core.bootstrap.task_status_sink", task_status_sink)
    monkeypatch.setattr("core.bootstrap.asyncio.sleep", AsyncMock())

    bootstrap._register_shutdown_hooks()
    cleanup = next(
        item["callback"]
        for item in bootstrap.coordinator.cleanups
        if item["name"] == "stop_auxiliary"
    )

    await cleanup()

    cron.stop.assert_awaited_once()
    guard.stop_guards_async.assert_awaited_once()
    guard.stop_guards.assert_not_called()
    update.stop.assert_called_once()
    sleep_manager.stop.assert_called_once()
    task_status_sink.stop.assert_awaited_once()
