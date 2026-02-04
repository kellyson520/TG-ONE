import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.comment_button_filter import CommentButtonFilter
from types import SimpleNamespace

@pytest.fixture
def comment_button_filter():
    return CommentButtonFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.only_rss = False
    context.rule.enable_comment_button = True
    context.rule.is_send_over_media_size_message = False
    
    context.event = MagicMock()
    context.event.chat_id = -1001234567890
    context.event.message = MagicMock()
    context.event.message.id = 100
    context.event.message.media = None
    context.event.message.grouped_id = None
    context.event.message.date = None
    
    context.original_message_text = "hello"
    context.client = AsyncMock()
    context.buttons = None
    context.is_media_group = False
    return context

@pytest.mark.asyncio
async def test_comment_button_filter_skip_if_disabled(comment_button_filter, mock_context):
    mock_context.rule.enable_comment_button = False
    result = await comment_button_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_comment_button_filter_not_broadcast(comment_button_filter, mock_context):
    mock_main = MagicMock()
    mock_main.user_client = MagicMock() # Use MagicMock to avoid coroutine issues with methods
    
    mock_resolver = AsyncMock()
    channel_entity = MagicMock()
    channel_entity.broadcast = False # Not a channel
    mock_resolver.resolve_single_entity.return_value = channel_entity
    
    with patch("filters.comment_button_filter.get_main_module", return_value=mock_main):
        with patch("core.helpers.entity_optimization.get_entity_resolver", return_value=mock_resolver):
            result = await comment_button_filter._process(mock_context)
            assert result is True
            assert not hasattr(mock_context, 'comment_link')

@pytest.mark.asyncio
async def test_comment_button_filter_success_public(comment_button_filter, mock_context):
    mock_main = MagicMock()
    mock_main.user_client = AsyncMock()
    
    mock_resolver = AsyncMock()
    channel_entity = MagicMock()
    channel_entity.id = -1001234567890
    channel_entity.username = "my_channel"
    channel_entity.broadcast = True
    
    linked_group = MagicMock()
    linked_group.id = 987654
    
    mock_resolver.resolve_single_entity.side_effect = [channel_entity, linked_group]
    
    # Mock client call (client is used as client(Request))
    mock_full = MagicMock()
    mock_full.full_chat.linked_chat_id = 987654
    mock_main.user_client.return_value = mock_full
    
    # Mock methods of client
    mock_main.user_client.get_messages = AsyncMock(return_value=[])
    
    with patch("filters.comment_button_filter.get_main_module", return_value=mock_main):
        with patch("core.helpers.entity_optimization.get_entity_resolver", return_value=mock_resolver):
            with patch("asyncio.sleep", return_value=None):
                result = await comment_button_filter._process(mock_context)
                
                assert result is True
                assert mock_context.comment_link == "https://t.me/my_channel/100?comment=1"
                assert len(mock_context.buttons) == 1
                assert mock_context.buttons[0][0].text == "💬 查看评论区"

@pytest.mark.asyncio
async def test_comment_button_filter_media_group(comment_button_filter, mock_context):
    mock_context.event.message.grouped_id = 555
    mock_context.is_media_group = True # Set by previous filters
    
    mock_main = MagicMock()
    mock_main.user_client = AsyncMock()
    
    mock_resolver = AsyncMock()
    channel_entity = MagicMock()
    channel_entity.id = -1001234567890
    channel_entity.broadcast = True
    channel_entity.username = None # Private channel
    
    linked_group = MagicMock()
    mock_resolver.resolve_single_entity.side_effect = [channel_entity, linked_group]
    
    mock_full = MagicMock()
    mock_full.full_chat.linked_chat_id = 987654
    mock_main.user_client.return_value = mock_full
    
    # Mock iter_messages for media group search
    class AsyncIter:
        def __init__(self, msgs): self.msgs = msgs
        def __aiter__(self): return self
        async def __anext__(self):
            if not self.msgs: raise StopAsyncIteration
            return self.msgs.pop(0)
            
    m1 = MagicMock(id=98)
    m1.grouped_id = 555
    m2 = MagicMock(id=100)
    m2.grouped_id = 555
    
    # Crucial: iter_messages must be a regular mock returning the iterator
    mock_main.user_client.iter_messages = MagicMock(return_value=AsyncIter([m1, m2]))
    mock_main.user_client.get_messages = AsyncMock(return_value=[])
    
    with patch("filters.comment_button_filter.get_main_module", return_value=mock_main):
        with patch("core.helpers.entity_optimization.get_entity_resolver", return_value=mock_resolver):
            with patch("asyncio.sleep", return_value=None):
                result = await comment_button_filter._process(mock_context)
                
                assert result is True
                assert mock_context.comment_link == "https://t.me/c/1234567890/98?comment=1"
                # For media group, buttons are skipped in CommentButtonFilter (ReplyFilter adds them)
                assert mock_context.buttons is None
