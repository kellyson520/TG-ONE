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
async def test_handle_prompt_setting_ai_prompt():
    # 模拟设置 AI 提示词
    event = MagicMock()
    event.message.text = "New AI Prompt"
    event.message.chat_id = 123
    event.message.id = 456
    
    client = AsyncMock()
    message_mock = AsyncMock()
    
    # Mock database session and rule
    mock_rule = MagicMock(spec=ForwardRule)
    mock_rule.id = 1
    mock_rule.enable_sync = False
    
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_rule
    
    # Mock context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.prompt_handlers.get_bot_client", new_callable=AsyncMock, return_value=client), \
         patch("handlers.prompt_handlers.async_delete_user_message") as mock_del_user, \
         patch("handlers.button.button_helpers.create_ai_settings_buttons", return_value=[]) as mock_buttons, \
         patch("handlers.prompt_handlers.get_ai_settings_text", return_value="Settings Text") as mock_text:
        
        sender_id = 1
        chat_id = 123
        current_state = "set_ai_prompt:1"
        
        result = await handle_prompt_setting(event, client, sender_id, chat_id, current_state, message_mock)
        
        assert result is True
        # 验证 rule 属性更新
        assert mock_rule.ai_prompt == "New AI Prompt"
        # 验证 session 方法调用
        mock_session.get.assert_called_once()
        # 验证消息删除
        message_mock.delete.assert_called_once()

@pytest.mark.asyncio
async def test_handle_prompt_setting_add_keywords():
    # 模拟添加关键词状态 kw_add:1
    event = MagicMock()
    event.message.text = "key1\nkey2"
    
    # Mock database session context manager
    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session

    with patch("handlers.prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("repositories.db_operations.DBOperations.create", new_callable=AsyncMock) as mock_db_ops, \
         patch("handlers.prompt_handlers.send_message_and_delete") as mock_send_del, \
         patch("handlers.prompt_handlers.get_bot_client", new_callable=AsyncMock, return_value=AsyncMock()):
        
        db_ops_inst = AsyncMock()
        mock_db_ops.return_value = db_ops_inst
        
        result = await handle_prompt_setting(event, AsyncMock(), 1, 123, "kw_add:1", MagicMock())
        
        assert result is True
        db_ops_inst.add_keywords.assert_called_once()
        args = db_ops_inst.add_keywords.call_args[0]
        assert args[2] == ["key1", "key2"]
