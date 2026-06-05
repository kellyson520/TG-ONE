import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.init_filter import InitFilter
from types import SimpleNamespace
from telethon.tl.types import DocumentAttributeVideo

@pytest.fixture
def init_filter():
    return InitFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.event = MagicMock()
    context.event.client = AsyncMock()
    context.event.message = MagicMock()
    context.event.message.grouped_id = None
    context.event.message.id = 100
    context.event.chat_id = 12345
    context.errors = []
    context.media_group_messages = []
    return context

@pytest.mark.asyncio
async def test_init_filter_basic(init_filter, mock_context):
    result = await init_filter._process(mock_context)
    assert result is True
    # Verify cleanup logic
    assert mock_context.dup_signatures == []

@pytest.mark.asyncio
async def test_init_filter_media_group_cache_hit(init_filter, mock_context):
    mock_context.event.message.grouped_id = 999
    mock_context.event.chat_id = 12345
    
    cached_data = {
        'text': "cached caption",
        'buttons': [[MagicMock()]]
    }
    
    with patch("core.cache.unified_cache.get_smart_cache") as mock_get_cache:
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.get.return_value = cached_data
        
        await init_filter._process(mock_context)
        
        # Verify cache was used
        assert mock_context.message_text == "cached caption"
        assert mock_context.buttons == cached_data['buttons']
        # Ensure iter_messages was NOT called
        mock_context.event.client.iter_messages.assert_not_called()
        # Verify cache key includes chat_id
        mock_cache.get.assert_called_with("media_group_ctx:12345:999")

@pytest.mark.asyncio
async def test_init_filter_media_group_cache_miss_and_store(init_filter, mock_context):
    mock_context.event.message.grouped_id = 888
    mock_context.event.chat_id = 54321
    
    # Mock iter_messages
    mock_msg = MagicMock()
    mock_msg.grouped_id = 888
    mock_msg.text = "fresh caption"
    mock_msg.buttons = None
    
    class AsyncIter:
        def __init__(self, items):
            self.items = items
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    mock_context.event.client.iter_messages = MagicMock(return_value=AsyncIter([mock_msg]))
    
    with patch("core.cache.unified_cache.get_smart_cache") as mock_get_cache:
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.get.return_value = None # Miss
        await init_filter._process(mock_context)
        
        assert mock_context.message_text == "fresh caption"
        # Verify it was stored in cache with correct key and TTL
        mock_cache.set.assert_called_once()
        args, kwargs = mock_cache.set.call_args
        assert args[0] == "media_group_ctx:54321:888"
        assert args[1]['text'] == "fresh caption"
        assert kwargs.get('ttl') == 30

@pytest.mark.asyncio
async def test_init_filter_iter_messages_error(init_filter, mock_context):
    mock_context.event.message.grouped_id = 123456
    with patch("core.cache.unified_cache.get_smart_cache") as mock_get_cache:
        mock_get_cache.return_value = MagicMock()
        mock_get_cache.return_value.get.return_value = None
        
        mock_context.event.client.iter_messages.side_effect = Exception("iter error")
        
        result = await init_filter._process(mock_context)
        assert result is True # Should not crash
        assert any("收集媒体组消息错误" in e for e in mock_context.errors)
