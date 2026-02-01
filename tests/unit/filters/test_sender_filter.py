import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.sender_filter import SenderFilter
from types import SimpleNamespace

@pytest.fixture
def sender_filter():
    return SenderFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.target_chat = SimpleNamespace(telegram_chat_id="123456", name="Target")
    context.rule.message_mode = "HTML"
    context.rule.is_preview = "on" 
    context.rule.enable_only_push = False
    context.rule.enable_push = False
    context.rule.force_pure_forward = False
    
    context.client = AsyncMock()
    context.event = MagicMock()
    context.event.chat_id = 987654
    context.event.message.id = 1
    context.event.message.grouped_id = None
    
    context.should_forward = True
    context.message_text = "hello"
    context.sender_info = "From: user\n"
    context.time_info = "\nTime: now"
    context.original_link = "\nOriginal: link"
    context.buttons = None
    context.media_files = []
    context.skipped_media = []
    context.is_media_group = False
    context.media_group_messages = []
    context.errors = []
    context.forwarded_messages = []
    
    return context

@pytest.mark.asyncio
async def test_sender_filter_skip_if_not_forward(sender_filter, mock_context):
    mock_context.should_forward = False
    result = await sender_filter._process(mock_context)
    assert result is False

@pytest.mark.asyncio
async def test_sender_filter_text_only(sender_filter, mock_context):
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        
        result = await sender_filter._process(mock_context)
        
        assert result is True
        mock_context.client.send_message.assert_called_once()
        args, kwargs = mock_context.client.send_message.call_args
        assert kwargs['parse_mode'] == 'HTML'

@pytest.mark.asyncio
async def test_sender_filter_pure_forward(sender_filter, mock_context):
    mock_context.rule.force_pure_forward = True
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("services.queue_service.forward_messages_queued", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = [MagicMock()]
            
            with patch.object(SenderFilter, "_record_forward", new_callable=AsyncMock) as mock_record:
                result = await sender_filter._process(mock_context)
                
                assert result is True
                mock_forward.assert_called_once()

@pytest.mark.asyncio
async def test_sender_filter_send_file(sender_filter, mock_context):
    mock_context.media_files = ["temp/file.jpg"]
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("os.remove") as mock_remove:
            result = await sender_filter._process(mock_context)
            
            assert result is True
            mock_context.client.send_file.assert_called_once()
            mock_remove.assert_called_once_with("temp/file.jpg")
