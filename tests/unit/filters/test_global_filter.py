import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from filters.global_filter import GlobalFilter
from types import SimpleNamespace

@pytest.fixture
def global_filter():
    return GlobalFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.event = MagicMock()
    context.event.message.media = None
    context.event.message.message = "some text"
    context.should_forward = True
    return context

@pytest.fixture
def mock_forward_manager():
    with patch("handlers.button.forward_management.forward_manager") as mock:
        future = MagicMock()
        future.get_global_media_settings = AsyncMock(return_value={
            'allow_text': True,
            'allow_emoji': True,
            'media_types': {'photo': True, 'video': True}
        })
        mock.return_value = future # Wait, mock is the module/object forward_manager
        
        # Correctly configure the existing mock object
        mock.get_global_media_settings = AsyncMock(return_value={
            'allow_text': True,
            'allow_emoji': True,
            'media_types': {'photo': True, 'video': True}
        })
        
        yield mock

@pytest.mark.asyncio
async def test_global_filter_allow_text(global_filter, mock_context, mock_forward_manager):
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is True

@pytest.mark.asyncio
async def test_global_filter_block_text(global_filter, mock_context, mock_forward_manager):
    # Mock settings to block text
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': False,
        'allow_emoji': True
    }
    
    result = await global_filter._process(mock_context)
    assert result is False
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_block_emoji_only(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'allow_emoji': False
    }
    # Regex in GlobalFilter likely doesn't match spaces for pure emoji check
    mock_context.event.message.message = "😀😂"
    
    result = await global_filter._process(mock_context)
    assert result is False
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_allow_mixed_emoji(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'allow_emoji': False
    }
    mock_context.event.message.message = "Hello 😀"
    
    result = await global_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_global_filter_block_media_type(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_types': {'image': False} # Key is 'image', not 'photo'
    }
    
    # Mock photo media
    mock_media = MagicMock()
    mock_media.photo = True
    mock_media.document = None
    mock_media.video = None
    mock_media.audio = None
    mock_media.voice = None
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = "" # Empty string, not None
    
    result = await global_filter._process(mock_context)
    
    # With allow_text=True, function returns True but sets should_forward based on text
    assert result is True 
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_block_voice(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_types': {'voice': False}
    }
    
    mock_media = MagicMock()
    mock_media.photo = None
    mock_media.voice = True
    mock_media.audio = None
    mock_media.video = None
    mock_media.document = None
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_block_video_document(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_types': {'video': False}
    }
    
    mock_media = MagicMock()
    mock_media.photo = None
    mock_media.voice = None
    mock_media.audio = None
    mock_media.video = None
    # Simulate a document that is a video
    class DocumentAttributeVideo: pass
    video_attr = DocumentAttributeVideo()
    
    mock_doc = MagicMock()
    mock_doc.attributes = [video_attr]
    mock_media.document = mock_doc
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_duration_limit(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_duration_enabled': True,
        'duration_max_seconds': 10
    }
    
    mock_media = MagicMock()
    mock_media.voice = MagicMock()
    mock_media.voice.duration = 20 # Exceeds limit
    # Set other types to None
    mock_media.photo = None
    mock_media.video = None
    mock_media.audio = None
    mock_media.document = None
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is False
