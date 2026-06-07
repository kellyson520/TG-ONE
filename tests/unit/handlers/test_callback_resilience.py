import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_handle_callback_logs_answer_failure_after_handler_error(caplog):
    """业务处理失败后的错误提示发送失败也必须可观测。"""
    from handlers.button.callback.callback_handlers import handle_callback

    async def broken_handler(event):
        raise RuntimeError("handler boom")

    event = AsyncMock()
    event.data = b"broken:1"
    event.answer = AsyncMock(side_effect=RuntimeError("answer down"))

    with patch("handlers.button.callback.callback_handlers.callback_router") as mock_router:
        mock_router.match.return_value = (broken_handler, {})

        with caplog.at_level(logging.WARNING, logger="handlers.button.callback.callback_handlers"):
            await handle_callback(event)

    assert "回调错误提示发送失败" in caplog.text
    assert "answer down" in caplog.text


@pytest.mark.asyncio
async def test_close_admin_panel_logs_delete_failure(caplog):
    """关闭管理面板失败不应静默吞掉。"""
    from handlers.button.callback.admin_callback import callback_close_admin_panel

    event = AsyncMock()
    event.delete = AsyncMock(side_effect=RuntimeError("delete denied"))
    event.answer = AsyncMock()

    with caplog.at_level(logging.WARNING, logger="handlers.button.callback.admin_callback"):
        await callback_close_admin_panel(event, None, None, None, None)

    assert "关闭管理面板失败" in caplog.text
    assert "delete denied" in caplog.text


@pytest.mark.asyncio
async def test_save_message_filter_logs_answer_failure_and_refreshes_menu(caplog):
    """保存筛选配置的提示失败时仍应刷新菜单并记录原因。"""
    from handlers.button.strategies.settings import SettingsMenuStrategy

    event = AsyncMock()
    event.answer = AsyncMock(side_effect=RuntimeError("answer down"))

    with patch(
        "handlers.button.new_menu_system.new_menu_system.show_delete_session_messages_menu",
        new_callable=AsyncMock,
    ) as mock_show:
        with caplog.at_level(logging.WARNING, logger="handlers.button.strategies.settings"):
            await SettingsMenuStrategy().handle(event, "save_message_filter")

    mock_show.assert_awaited_once_with(event)
    assert "保存筛选配置提示发送失败" in caplog.text
    assert "answer down" in caplog.text


@pytest.mark.asyncio
async def test_rule_dedup_settings_logs_invalid_custom_config(caplog, monkeypatch):
    from handlers.button.callback.modules import rule_dedup_settings as module

    rule = SimpleNamespace(custom_config="{bad-json")
    event = SimpleNamespace(answer=AsyncMock())
    message = SimpleNamespace(edit=AsyncMock())

    monkeypatch.setattr(
        module,
        "container",
        SimpleNamespace(
            rule_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=rule)),
        ),
    )
    monkeypatch.setattr(
        module,
        "dedup_service",
        SimpleNamespace(get_dedup_config=AsyncMock(return_value={"config": {}})),
    )
    monkeypatch.setattr(
        module.Button,
        "inline",
        staticmethod(lambda text, data: {"text": text, "data": data}),
    )

    with caplog.at_level(logging.WARNING, logger=module.__name__):
        await module.callback_rule_dedup_settings(event, 42, message)

    message.edit.assert_awaited_once()
    assert "规则去重配置解析失败" in caplog.text
    assert "rule_id=42" in caplog.text
