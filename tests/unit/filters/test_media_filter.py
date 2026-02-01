import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.media_filter import MediaFilter
import os

@pytest.fixture
def media_filter():
    return MediaFilter()

from types import SimpleNamespace

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.enable_media_type_filter = False
    context.rule.enable_extension_filter = False
    context.rule.enable_media_size_filter = False
    context.rule.max_media_size = 0
    context.rule.media_allow_text = True
    context.rule.is_send_over_media_size_message = False
    context.rule.only_rss = False
    
    context.event = MagicMock()
    context.event.message = MagicMock()
    context.event.message.media = None
    context.event.message.grouped_id = None
    context.event.message.document = None
    
    context.errors = []
    context.media_files = []
    context.should_forward = True
    context.media_group_messages = []
    context.skipped_media = []
    return context

@pytest.mark.asyncio
async def test_media_filter_skip_no_media(media_filter, mock_context):
    mock_context.event.message.media = None
    result = await media_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_media_filter_single_media_pass(media_filter, mock_context):
    # Setup
    mock_context.event.message.media = MagicMock(spec=['photo', 'document', 'video', 'audio', 'voice'])
    mock_context.event.message.media.photo = MagicMock()
    mock_context.event.message.media.document = None
    mock_context.event.message.media.video = None
    mock_context.event.message.media.audio = None
    mock_context.event.message.media.voice = None
    
    mock_context.rule.enable_media_size_filter = True
    mock_context.rule.max_media_size = 100 # 100MB
    mock_context.rule.force_pure_forward = False
    mock_context.rule.enable_push = False
    
    # Mock download
    with patch.object(MediaFilter, "_download_media_optimized", new_callable=AsyncMock) as mock_download:
        mock_download.return_value = "temp/path/file.jpg"
        
        with patch.object(MediaFilter, "_get_media_size_optimized", new_callable=AsyncMock) as mock_size:
            mock_size.return_value = 1024 * 1024 # 1MB
            
            result = await media_filter._process(mock_context)
            
            assert result is True
            mock_download.assert_called_once()
            assert "temp/path/file.jpg" in mock_context.media_files

@pytest.mark.asyncio
async def test_media_filter_size_limit_hit(media_filter, mock_context):
    # Setup
    mock_context.event.message.media = MagicMock(spec=['photo', 'document', 'video', 'audio', 'voice'])
    mock_context.event.message.media.photo = MagicMock()
    mock_context.rule.enable_media_size_filter = True
    mock_context.rule.max_media_size = 5 # 5MB limit
    mock_context.rule.media_allow_text = False
    mock_context.rule.is_send_over_media_size_message = False
    mock_context.rule.force_pure_forward = False
    mock_context.rule.enable_push = False
    
    with patch.object(MediaFilter, "_get_media_size_optimized", new_callable=AsyncMock) as mock_size:
        mock_size.return_value = 10 * 1024 * 1024 # 10MB
        
        result = await media_filter._process(mock_context)
        
        assert result is True
        assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_media_filter_media_type_blocked(media_filter, mock_context):
    # Setup
    mock_context.event.message.media = MagicMock()
    mock_context.event.message.media.photo = MagicMock() # It's a photo
    mock_context.rule.enable_media_type_filter = True
    mock_context.rule.media_allow_text = False
    
    # Mock database session for MediaTypes
    mock_media_types = MagicMock()
    mock_media_types.photo = True # Photo is BLOCKED if this returns True in _is_media_type_blocked
    
    # Actually _is_media_type_blocked returns media_types.photo which means BLOCKED=True
    
    with patch("core.container.container.db.session") as mock_session:
        # Complex mocking for sqlalchemy result
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_media_types
        execute_mock = AsyncMock(return_value=mock_res)
        
        session_mock = AsyncMock()
        session_mock.execute = execute_mock
        mock_session.return_value.__aenter__.return_value = session_mock
        
        result = await media_filter._process(mock_context)
        
        assert result is True
        assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_media_filter_media_group(media_filter, mock_context):
    # Setup
    mock_context.event.message.grouped_id = 12345
    mock_context.event.message.media = MagicMock()
    mock_context.rule.enable_media_size_filter = True
    mock_context.rule.max_media_size = 100
    mock_context.rule.media_allow_text = True
    
    # Mock media_service.get_media_group_messages
    mock_msg1 = MagicMock()
    mock_msg1.id = 101
    mock_msg1.media = MagicMock()
    mock_msg1.media.photo = MagicMock()
    
    # Correct patching for top-level imports
    with patch("filters.media_filter.media_service.get_media_group_messages", new_callable=AsyncMock) as mock_get_group:
        mock_get_group.return_value = [mock_msg1]
        
        # Mock database session
        with patch("core.container.container.db.session") as mock_session:
             mock_session.return_value.__aenter__.return_value = AsyncMock()
             
             with patch("filters.media_filter.extract_message_signature") as mock_sig:
                 mock_sig.return_value = ("sig1", None)
                 
                 # Patching instance method to avoid API calls
                 with patch.object(MediaFilter, "_get_media_size_optimized", new_callable=AsyncMock) as mock_size:
                     mock_size.return_value = 1024 * 1024 # 1MB
                     
                     result = await media_filter._process(mock_context)
                     
                     assert result is True
                     assert len(mock_context.media_group_messages) == 1
                     assert mock_context.media_group_messages[0].id == 101
