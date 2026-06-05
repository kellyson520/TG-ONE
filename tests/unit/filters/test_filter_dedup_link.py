import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.global_filter import GlobalFilter
from filters.keyword_filter import KeywordFilter
from types import SimpleNamespace

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.message_text = "test text"
    context.event = MagicMock()
    context.event.message.media = MagicMock()
    context.event.message.media.photo = MagicMock()
    context.event.message.message = "test text"
    context.should_forward = True
    context.media_blocked = False
    
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.enable_dedup = True
    context.rule.target_chat = SimpleNamespace(telegram_chat_id="123456")
    return context

@pytest.mark.asyncio
async def test_global_filter_media_blocked_with_text(mock_context):
    # 模拟全局设置：关闭图片，开启文本
    mock_settings = {
        'allow_text': True,
        'media_types': {'image': False}
    }
    
    with patch("handlers.button.forward_management.forward_manager.get_global_media_settings", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_settings
        
        filter = GlobalFilter()
        result = await filter._process(mock_context)
        
        assert result is True
        assert mock_context.media_blocked is True
        assert mock_context.should_forward is True

@pytest.mark.asyncio
async def test_global_filter_media_blocked_no_text(mock_context):
    # 模拟全局设置：关闭图片，开启文本
    mock_settings = {
        'allow_text': True,
        'media_types': {'image': False}
    }
    mock_context.event.message.message = "" # 无文本
    
    with patch("handlers.button.forward_management.forward_manager.get_global_media_settings", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_settings
        
        filter = GlobalFilter()
        result = await filter._process(mock_context)
        
        assert result is False # 应该中断链
        assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_keyword_filter_respects_media_blocked(mock_context):
    mock_context.media_blocked = True # 模拟已被 GlobalFilter 标记
    
    filter = KeywordFilter()
    
    with patch("services.dedup.engine.smart_deduplicator.check_duplicate", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = (False, "")
        with patch("services.rule.filter.RuleFilterService.check_keywords", return_value=True):
            await filter._process(mock_context)
            
            # 验证调用时传了 skip_media_sig=True
            args, kwargs = mock_check.call_args
            assert kwargs['skip_media_sig'] is True
