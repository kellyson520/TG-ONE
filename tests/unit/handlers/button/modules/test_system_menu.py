import builtins
import logging
from unittest.mock import AsyncMock

import pytest

from handlers.button.modules import system_menu as system_menu_module
from handlers.button.modules.system_menu import SystemMenu


@pytest.mark.asyncio
async def test_system_overview_logs_unreadable_log_file(
    tmp_path,
    monkeypatch,
    caplog,
):
    menu = SystemMenu()
    menu._render_page = AsyncMock()
    event = AsyncMock()
    good_log = tmp_path / "good.log"
    bad_log = tmp_path / "bad.log"
    good_log.write_text("INFO booted\nERROR failed once\n", encoding="utf-8")
    bad_log.write_text("WARNING unreadable\n", encoding="utf-8")
    original_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("bad.log"):
            raise OSError("cannot read log")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(system_menu_module, "PSUTIL_AVAILABLE", False)
    monkeypatch.setattr(system_menu_module.settings, "LOG_DIR", tmp_path)
    monkeypatch.setattr(system_menu_module.settings, "DB_DIR", tmp_path)
    monkeypatch.setattr(builtins, "open", fake_open)
    caplog.set_level(logging.DEBUG, logger="handlers.button.modules.system_menu")

    await menu.show_system_overview(event)

    menu._render_page.assert_awaited_once()
    assert "SystemMenu failed to read log file" in caplog.text
    assert str(bad_log) in caplog.text
