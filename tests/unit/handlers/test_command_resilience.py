import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_common_search_handler_logs_command_delete_failure(caplog):
    from handlers.commands.rule_commands import _common_search_handler

    event = SimpleNamespace(
        client=object(),
        chat_id=12345,
        message=SimpleNamespace(id=67890, text="/search keyword"),
    )
    search_system = SimpleNamespace(search=AsyncMock(return_value=object()))

    with patch("core.helpers.search_system.get_search_system", return_value=search_system), \
         patch("core.helpers.search_system.SearchFilter", return_value=object()), \
         patch("core.container.container.user_client", object()), \
         patch("handlers.search_ui_manager.SearchUIManager.generate_search_message", return_value="result"), \
         patch("handlers.search_ui_manager.SearchUIManager.generate_pagination_buttons", return_value=[]), \
         patch("core.helpers.auto_delete.async_delete_user_message", new_callable=AsyncMock, side_effect=RuntimeError("delete failed")), \
         patch("core.helpers.auto_delete.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        with caplog.at_level(logging.WARNING, logger="handlers.commands.rule_commands"):
            await _common_search_handler(event, ["/search", "keyword"], search_type="all")

    mock_reply.assert_awaited_once()
    assert "搜索命令删除用户消息失败" in caplog.text
    assert "chat_id=12345" in caplog.text
    assert "message_id=67890" in caplog.text
    assert "delete failed" in caplog.text


@pytest.mark.asyncio
async def test_handle_command_logs_floodwait_recovery_response_failure(caplog):
    import handlers.bot_handler as bot_handler
    from telethon.errors import FloodWaitError

    flood_wait = FloodWaitError.__new__(FloodWaitError)
    flood_wait.seconds = 1

    event = SimpleNamespace(
        message=SimpleNamespace(text="/start"),
        sender_id=111,
        chat_id=222,
        get_chat=AsyncMock(return_value=SimpleNamespace(id=222)),
        respond=AsyncMock(side_effect=RuntimeError("respond down")),
    )

    with patch("handlers.bot_handler.asyncio.sleep", new_callable=AsyncMock), \
         patch("handlers.bot_handler.is_admin", new_callable=AsyncMock) as is_admin, \
         patch("handlers.bot_handler.get_user_id", new_callable=AsyncMock) as get_user_id, \
         patch("handlers.bot_handler.handle_start_command", new_callable=AsyncMock) as start_cmd:
        is_admin.return_value = True
        get_user_id.return_value = 999
        start_cmd.side_effect = flood_wait

        with caplog.at_level(logging.WARNING, logger="handlers.bot_handler"):
            await bot_handler.handle_command(object(), event)

    assert "FloodWait" in caplog.text
    assert "respond down" in caplog.text
