import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.button.modules import history as history_module
from handlers.button.modules.history import HistoryModule
from services.network import telegram_utils


@pytest.mark.asyncio
async def test_time_range_selection_logs_session_fallback_failures(
    monkeypatch,
    caplog,
):
    menu = HistoryModule()
    event = SimpleNamespace(
        chat_id=12345,
        sender_id=67890,
        respond=AsyncMock(),
    )
    session = SimpleNamespace(
        get_chat_message_date_range=AsyncMock(
            side_effect=RuntimeError("date range failed")
        ),
        get_time_picker_context=MagicMock(
            side_effect=[
                RuntimeError("context for display failed"),
                RuntimeError("context for route failed"),
            ]
        ),
        get_time_range_display=AsyncMock(),
    )
    safe_edit = AsyncMock(return_value=True)

    monkeypatch.setattr(history_module, "session_manager", session)
    monkeypatch.setattr(telegram_utils, "safe_edit", safe_edit)
    caplog.set_level(logging.DEBUG, logger="handlers.button.modules.history")

    await menu.show_time_range_selection(event)

    safe_edit.assert_awaited_once()
    event.respond.assert_not_awaited()
    session.get_time_range_display.assert_not_awaited()
    assert "HistoryModule failed to get message date range" in caplog.text
    assert "HistoryModule failed to get time range display" in caplog.text
    assert "HistoryModule failed to get time picker context" in caplog.text
    assert "chat_id=12345" in caplog.text
    assert "sender_id=67890" in caplog.text


@pytest.mark.asyncio
async def test_history_menu_safe_edit_fallbacks_log_context(
    monkeypatch,
    caplog,
):
    menu = HistoryModule()
    event = SimpleNamespace(
        chat_id=12345,
        sender_id=67890,
        respond=AsyncMock(),
    )
    forward_manager = SimpleNamespace(
        get_global_media_settings=AsyncMock(
            return_value={
                "HISTORY_MESSAGE_LIMIT": 2000,
                "allow_text": True,
                "media_types": {
                    "image": True,
                    "video": True,
                    "audio": False,
                    "voice": True,
                    "document": False,
                },
            }
        ),
        create_media_duration_settings_buttons=AsyncMock(return_value=[["old"]]),
    )
    safe_edit = AsyncMock(side_effect=RuntimeError("edit failed"))

    monkeypatch.setattr(history_module, "forward_manager", forward_manager)
    monkeypatch.setattr(history_module.settings, "HISTORY_MESSAGE_LIMIT", 2000)
    monkeypatch.setattr(telegram_utils, "safe_edit", safe_edit)
    caplog.set_level(logging.DEBUG, logger="handlers.button.modules.history")

    await menu.show_message_filter_menu(event)
    await menu.show_media_types(event)
    await menu.show_media_duration_settings(event)
    await menu.show_message_limit_menu(event)

    assert safe_edit.await_count == 4
    assert event.respond.await_count == 4
    assert "HistoryModule failed to edit message filter menu" in caplog.text
    assert "HistoryModule failed to edit media types menu" in caplog.text
    assert "HistoryModule failed to edit media duration settings" in caplog.text
    assert "HistoryModule failed to edit message limit menu" in caplog.text
    assert "chat_id=12345" in caplog.text
    assert "sender_id=67890" in caplog.text
