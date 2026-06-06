import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.prompt_handlers import handle_prompt_setting
from models.models import ForwardRule

@pytest.mark.asyncio
async def test_handle_prompt_setting_no_state():
    # 测试无状态时返回 False
    event = MagicMock()
    client = MagicMock()
    result = await handle_prompt_setting(event, client, 1, 1, None, MagicMock())
    assert result is False


@pytest.mark.asyncio
async def test_handle_prompt_setting_history_limit():
    event = MagicMock()
    event.message.text = "2,500"
    client = AsyncMock()
    sender_id = 1
    chat_id = 123
    state = {"state": "set_history_limit", "state_type": "history"}

    with patch("handlers.prompt_handlers.session_manager") as mock_sm, \
         patch("handlers.prompt_handlers.get_bot_client", new_callable=AsyncMock, return_value=client), \
         patch("handlers.prompt_handlers.send_message_and_delete", new_callable=AsyncMock) as mock_send:
        mock_sm.user_sessions = {sender_id: {chat_id: state}}
        mock_sm.set_history_message_limit = AsyncMock(
            return_value={"success": True, "limit": 2500}
        )

        result = await handle_prompt_setting(
            event, client, sender_id, chat_id, "set_history_limit", MagicMock()
        )

        assert result is True
        mock_sm.set_history_message_limit.assert_awaited_once_with("2500")
        assert sender_id not in mock_sm.user_sessions
        mock_send.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_prompt_setting_ai_prompt():
    # 模拟设置 AI 提示词
    event = MagicMock()
    event.message.text = "New AI Prompt"
    event.message.chat_id = 123
    event.message.id = 456
    
    client = AsyncMock()
    message_mock = AsyncMock()
    
    mock_rule = MagicMock(spec=ForwardRule)
    mock_rule.id = 1
    mock_rule.enable_sync = False

    with patch("handlers.prompt_handlers.container") as mock_container, \
         patch("handlers.prompt_handlers.get_bot_client", new_callable=AsyncMock, return_value=client), \
         patch("handlers.prompt_handlers.async_delete_user_message") as mock_del_user, \
         patch("handlers.button.button_helpers.create_ai_settings_buttons", return_value=[]) as mock_buttons, \
         patch("handlers.prompt_handlers.get_ai_settings_text", return_value="Settings Text") as mock_text:
        mock_container.rule_service.toggle_rule_setting = AsyncMock(
            return_value={"success": True}
        )
        mock_container.rule_repo.get_by_id = AsyncMock(return_value=mock_rule)
        
        sender_id = 1
        chat_id = 123
        current_state = "set_ai_prompt:1"
        
        result = await handle_prompt_setting(event, client, sender_id, chat_id, current_state, message_mock)
        
        assert result is True
        mock_container.rule_service.toggle_rule_setting.assert_awaited_once_with(
            1, "ai_prompt", "New AI Prompt"
        )
        # 验证消息删除
        message_mock.delete.assert_called_once()

@pytest.mark.asyncio
async def test_handle_prompt_setting_add_keywords():
    # 模拟添加关键词状态 kw_add:1
    event = MagicMock()
    event.message.text = "key1\nkey2"
    
    with patch("handlers.prompt_handlers.container") as mock_container, \
         patch("handlers.prompt_handlers.send_message_and_delete") as mock_send_del, \
         patch("handlers.prompt_handlers.get_bot_client", new_callable=AsyncMock, return_value=AsyncMock()):
        mock_container.rule_service.add_keywords = AsyncMock()
        
        result = await handle_prompt_setting(event, AsyncMock(), 1, 123, "kw_add:1", MagicMock())
        
        assert result is True
        mock_container.rule_service.add_keywords.assert_awaited_once_with(
            1, ["key1", "key2"], is_regex=False, is_negative=True
        )
