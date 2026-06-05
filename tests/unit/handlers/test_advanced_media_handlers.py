import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.advanced_media_prompt_handlers import (
    handle_duration_range_input, 
    handle_file_size_range_input, 
    handle_resolution_range_input,
    handle_advanced_media_prompt
)
from models.models import ForwardRule

@pytest.mark.asyncio
def create_mock_rule():
    rule = MagicMock(spec=ForwardRule)
    rule.id = 1
    rule.min_duration = 0
    rule.max_duration = 0
    rule.min_width = 0
    rule.min_height = 0
    rule.max_width = 0
    rule.max_height = 0
    rule.min_file_size = 0
    rule.max_file_size = 0
    return rule

@pytest.mark.asyncio
async def test_handle_duration_range_input_success():
    # 准备 Mock
    event = MagicMock()
    rule = create_mock_rule()
    
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        # 输入 "10 60"
        result = await handle_duration_range_input(event, 1, "10 60")
        
        assert result is True
        assert rule.min_duration == 10
        assert rule.max_duration == 60
        mock_session.commit.assert_called_once()
        mock_reply.assert_called_once()

@pytest.mark.asyncio
async def test_handle_file_size_range_input_units():
    # 测试不同单位 M, G
    event = MagicMock()
    rule = create_mock_rule()
    
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        # "100M 2G"
        result = await handle_file_size_range_input(event, 1, "100M 2G")
        
        assert result is True
        assert rule.min_file_size == 100 * 1024
        assert rule.max_file_size == 2 * 1024 * 1024

@pytest.mark.asyncio
async def test_handle_advanced_media_prompt_routing():
    user_id = 123
    chat_id = 456
    state = {
        "state": "waiting_duration_range",
        "message": {"rule_id": 1}
    }
    
    with patch("handlers.advanced_media_prompt_handlers.session_manager") as mock_sm, \
         patch("handlers.advanced_media_prompt_handlers.handle_duration_range_input", new_callable=AsyncMock) as mock_handler:
        
        mock_sm.user_sessions = {user_id: {chat_id: state}}
        mock_handler.return_value = True
        
        event = MagicMock()
        event.message.text = "10 60"
        
        result = await handle_advanced_media_prompt(event, user_id, chat_id)
        
        assert result is True
        mock_handler.assert_called_with(event, 1, "10 60")
        assert user_id not in mock_sm.user_sessions

@pytest.mark.asyncio
async def test_handle_duration_range_input_invalid():
    event = MagicMock()
    rule = create_mock_rule()
    
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        # 1. 非数字
        assert await handle_duration_range_input(event, 1, "abc") is False
        # 2. 负数
        assert await handle_duration_range_input(event, 1, "-10 20") is False
        # 3. 最小值 > 最大值
        assert await handle_duration_range_input(event, 1, "100 50") is False

@pytest.mark.asyncio
async def test_handle_resolution_range_input_success():
    event = MagicMock()
    rule = create_mock_rule()
    
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        # 输入 "1920 1080" (仅设置最小分辨率)
        result = await handle_resolution_range_input(event, 1, "1920 1080")
        assert result is True
        assert rule.min_width == 1920
        assert rule.min_height == 1080
        
        # 输入四个数 "0 0 3840 2160" (设置最大最小)
        result = await handle_resolution_range_input(event, 1, "0 0 3840 2160")
        assert result is True
        assert rule.max_width == 3840
        assert rule.max_height == 2160

@pytest.mark.asyncio
async def test_handle_file_size_range_input_invalid_format():
    event = MagicMock()
    rule = create_mock_rule()
    
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        # 非法格式
        assert await handle_file_size_range_input(event, 1, "100X") is False

@pytest.mark.asyncio
async def test_handle_advanced_media_prompt_no_state():
    user_id = 999
    chat_id = 888
    event = MagicMock()
    
    with patch("handlers.advanced_media_prompt_handlers.session_manager") as mock_sm:
        mock_sm.user_sessions = {}
        result = await handle_advanced_media_prompt(event, user_id, chat_id)
        assert result is False

@pytest.mark.asyncio
async def test_handle_resolution_range_input_invalid_args():
    event = MagicMock()
    rule = create_mock_rule()
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        assert await handle_resolution_range_input(event, 1, "1920") is False
        assert await handle_resolution_range_input(event, 1, "1920 1080 3840") is False

@pytest.mark.asyncio
async def test_handle_file_size_range_input_zero():
    event = MagicMock()
    rule = create_mock_rule()
    mock_session = AsyncMock()
    mock_session.get.return_value = rule
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    
    with patch("handlers.advanced_media_prompt_handlers.async_db_session", return_value=mock_cm), \
         patch("handlers.advanced_media_prompt_handlers.reply_and_delete", new_callable=AsyncMock) as mock_reply:
        
        assert await handle_file_size_range_input(event, 1, "0") is True
        assert rule.min_file_size == 0

@pytest.mark.asyncio
async def test_handle_advanced_media_prompt_invalid_context():
    user_id = 123
    chat_id = 456
    event = MagicMock()
    
    with patch("handlers.advanced_media_prompt_handlers.session_manager") as mock_sm:
        mock_sm.user_sessions = {user_id: {chat_id: {"state": "waiting_duration", "message": "string_not_dict"}}}
        assert await handle_advanced_media_prompt(event, user_id, chat_id) is False
        
        mock_sm.user_sessions = {user_id: {chat_id: {"state": "waiting_duration", "message": {}}}}
        assert await handle_advanced_media_prompt(event, user_id, chat_id) is False

