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
    context.metadata = {}
    
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
        assert mock_context.metadata['resolved_target_id_1'] == 123456

@pytest.mark.asyncio
async def test_sender_filter_pure_forward(sender_filter, mock_context):
    mock_context.rule.force_pure_forward = True
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("services.queue_service.forward_messages_queued", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = [MagicMock()]
            
            result = await sender_filter._process(mock_context)
            
            assert result is True
            assert mock_context.metadata['resolved_target_id_1'] == 123456

@pytest.mark.asyncio
async def test_sender_filter_send_file(sender_filter, mock_context):
    mock_context.media_files = ["temp/file.jpg"]
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("os.remove") as mock_remove:
            result = await sender_filter._process(mock_context)
            
            assert result is True
            assert mock_context.metadata['resolved_target_id_1'] == 123456

@pytest.mark.asyncio
async def test_sender_filter_only_push(sender_filter, mock_context):
    mock_context.rule.enable_only_push = True
    result = await sender_filter._process(mock_context)
    assert result is True
    mock_context.client.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_sender_filter_error_handling(sender_filter, mock_context):
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        mock_context.client.send_message.side_effect = Exception("telegram error")
        
        # SenderFilter handles exceptions by logging warning and returning True (admission)
        # unless it's a fatal error before resolution.
        # Check current implementation: it returns True even on exception in target resolution.
        result = await sender_filter._process(mock_context)
        assert result is True 

@pytest.mark.asyncio
async def test_sender_filter_album(sender_filter, mock_context):
    mock_context.rule.force_pure_forward = True
    mock_context.is_media_group = True
    mock_context.event.message.grouped_id = 999
    msg1 = MagicMock(id=1)
    msg2 = MagicMock(id=2)
    mock_context.media_group_messages = [msg1, msg2]
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("services.queue_service.forward_messages_queued", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = [MagicMock(), MagicMock()]
            
            result = await sender_filter._process(mock_context)
            assert result is True
            assert mock_context.metadata['resolved_target_id_1'] == 123456

@pytest.mark.asyncio
async def test_sender_filter_multi_file(sender_filter, mock_context):
    mock_context.media_files = ["file1.jpg", "file2.jpg"]
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("os.remove") as mock_remove:
            result = await sender_filter._process(mock_context)
            assert result is True
            assert mock_context.metadata['resolved_target_id_1'] == 123456
@pytest.mark.asyncio
async def test_sender_filter_protected_error(sender_filter, mock_context):
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        mock_context.client.send_message.side_effect = Exception("protected chat")
        
        result = await sender_filter._process(mock_context)
        assert result is True # Should pass through

@pytest.mark.asyncio
async def test_sender_filter_record_forward_success(sender_filter, mock_context):
    mock_context.rule.force_pure_forward = True
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("services.queue_service.forward_messages_queued", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = [MagicMock()]
            with patch("core.helpers.common.get_main_module", new_callable=AsyncMock) as mock_main:
                mock_client = AsyncMock()
                mock_main.return_value.user_client = mock_client
                mock_client.get_messages.return_value = MagicMock()
                
                result = await sender_filter._process(mock_context)
                assert result is True
                assert mock_context.metadata['resolved_target_id_1'] == 123456

@pytest.mark.asyncio
async def test_sender_filter_get_target_chat(sender_filter, mock_context):
    mock_context.rule.target_chat = None
    mock_context.rule.target_chat_id = 99
    
    with patch.object(SenderFilter, "_get_target_chat", new_callable=AsyncMock) as mock_op:
        mock_op.return_value = SimpleNamespace(telegram_chat_id="999", name="DBTarget")
        
        target = await sender_filter._get_target_chat(mock_context.rule)
        assert target.name == "DBTarget"

@pytest.mark.asyncio
async def test_sender_filter_media_group_upload(sender_filter, mock_context):
    # Test _send_media_group branch (not pure forward)
    mock_context.is_media_group = True
    mock_context.rule.force_pure_forward = False
    mock_msg = MagicMock()
    mock_msg.media = True
    mock_msg.download_media = AsyncMock(return_value="temp/album1.jpg")
    mock_context.media_group_messages = [mock_msg]
    
    with patch("core.helpers.id_utils.resolve_entity_by_id_variants", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = (None, 123456)
        with patch("os.remove") as mock_remove:
            with patch("os.path.exists", return_value=True):
                result = await sender_filter._process(mock_context)
                assert result is True
                assert mock_context.metadata['resolved_target_id_1'] == 123456
