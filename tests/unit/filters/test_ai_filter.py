import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.ai_filter import AIFilter

@pytest.fixture
def ai_filter():
    return AIFilter()

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.rule = MagicMock()
    context.message_text = "test message"
    context.media_files = []
    context.is_media_group = False
    context.errors = []
    return context

@pytest.mark.asyncio
async def test_ai_filter_skip_non_ai(ai_filter, mock_context):
    mock_context.rule.is_ai = False
    result = await ai_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_ai_filter_basic_processing(ai_filter, mock_context):
    # Setup
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = False
    mock_context.rule.is_keyword_after_ai = False
    
    mock_ai_service = AsyncMock()
    mock_ai_service.process_message.return_value = "AI processed text"
    
    # Path of imports in filters/ai_filter.py
    with patch("services.ai_service.ai_service", mock_ai_service):
        result = await ai_filter._process(mock_context)
        
        assert result is True
        assert mock_context.message_text == "AI processed text"
        mock_ai_service.process_message.assert_called_once()

@pytest.mark.asyncio
async def test_ai_filter_with_images(ai_filter, mock_context):
    # Setup
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = True
    mock_context.rule.is_keyword_after_ai = False
    mock_context.media_files = ["path/to/img.png"]
    
    mock_ai_service = AsyncMock()
    mock_ai_service.process_message.return_value = "AI with image"
    
    mock_media_processor = AsyncMock()
    mock_media_processor.load_file_to_memory.return_value = b"image_data"
    
    with patch("services.ai_service.ai_service", mock_ai_service):
        with patch("services.media_service.ai_media_processor", mock_media_processor):
            result = await ai_filter._process(mock_context)
            
            assert result is True
            assert mock_context.message_text == "AI with image"
            mock_media_processor.load_file_to_memory.assert_called_once_with("path/to/img.png")
            # Verify images were passed to ai_service
            called_kwargs = mock_ai_service.process_message.call_args.kwargs
            assert called_kwargs["images"] == [b"image_data"]

@pytest.mark.asyncio
async def test_ai_filter_keyword_after_ai_fail(ai_filter, mock_context):
    # Setup
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = False
    mock_context.rule.is_keyword_after_ai = True
    
    mock_ai_service = AsyncMock()
    mock_ai_service.process_message.return_value = "bad content"
    
    with patch("services.ai_service.ai_service", mock_ai_service):
        with patch("filters.ai_filter.check_keywords", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            
            result = await ai_filter._process(mock_context)
            
            assert result is False
            assert mock_context.should_forward is False
@pytest.mark.asyncio
async def test_ai_filter_media_group_images(ai_filter, mock_context):
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = True
    mock_context.is_media_group = True
    
    mock_msg = MagicMock()
    mock_msg.photo = True
    mock_context.media_group_messages = [mock_msg]
    
    mock_ai_service = AsyncMock()
    mock_media_processor = AsyncMock()
    mock_media_processor.download_message_media_to_memory.return_value = b"group_img"
    
    with patch("services.ai_service.ai_service", mock_ai_service):
        with patch("services.media_service.ai_media_processor", mock_media_processor):
            await ai_filter._process(mock_context)
            called_kwargs = mock_ai_service.process_message.call_args.kwargs
            assert b"group_img" in called_kwargs["images"]

@pytest.mark.asyncio
async def test_ai_filter_single_media_download(ai_filter, mock_context):
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = True
    mock_context.media_files = [] # Not yet downloaded
    mock_context.event.message.media = MagicMock()
    
    mock_ai_service = AsyncMock()
    mock_media_processor = AsyncMock()
    mock_media_processor.download_message_media_to_memory.return_value = b"single_img"
    
    with patch("services.ai_service.ai_service", mock_ai_service):
        with patch("services.media_service.ai_media_processor", mock_media_processor):
            await ai_filter._process(mock_context)
            called_kwargs = mock_ai_service.process_message.call_args.kwargs
            assert b"single_img" in called_kwargs["images"]

@pytest.mark.asyncio
async def test_ai_filter_exception_handling(ai_filter, mock_context):
    mock_context.rule.is_ai = True
    
    mock_ai = AsyncMock()
    mock_ai.process_message.side_effect = Exception("critical error")
    
    with patch("services.ai_service.ai_service", mock_ai):
        result = await ai_filter._process(mock_context)
        # Should catch and return True (not block chain)
        assert result is True
        assert any("critical error" in str(e) for e in mock_context.errors)

@pytest.mark.asyncio
async def test_ai_filter_image_load_fail(ai_filter, mock_context):
    # Test case where load_file_to_memory returns None (simulating failure or empty)
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = True
    mock_context.media_files = ["corrupt.png"]
    
    mock_media_processor = AsyncMock()
    mock_media_processor.load_file_to_memory.return_value = None
    
    mock_ai = AsyncMock()
    
    with patch("services.media_service.ai_media_processor", mock_media_processor):
        with patch("services.ai_service.ai_service", mock_ai):
            await ai_filter._process(mock_context)
            
            # Should have called load... but passed empty list to ai_service
            mock_media_processor.load_file_to_memory.assert_called_once()
            called_kwargs = mock_ai.process_message.call_args.kwargs
            assert called_kwargs["images"] == []

@pytest.mark.asyncio
async def test_ai_filter_download_fail(ai_filter, mock_context):
    # Test case where download returns None
    mock_context.rule.is_ai = True
    mock_context.rule.enable_ai_upload_image = True
    mock_context.media_files = [] 
    mock_context.event.message.media = MagicMock()
    
    mock_media_processor = AsyncMock()
    mock_media_processor.download_message_media_to_memory.return_value = None
    
    mock_ai = AsyncMock()
    
    with patch("services.media_service.ai_media_processor", mock_media_processor):
        with patch("services.ai_service.ai_service", mock_ai):
            await ai_filter._process(mock_context)
            
            mock_media_processor.download_message_media_to_memory.assert_called_once()
            called_kwargs = mock_ai.process_message.call_args.kwargs
            assert called_kwargs["images"] == []

