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
async def test_global_filter_block_complex_emoji(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'allow_emoji': False
    }
    # Superhero emoji: 🦸‍♂️
    mock_context.event.message.message = "🦸‍♂️"
    result = await global_filter._process(mock_context)
    assert result is False
    
@pytest.mark.asyncio
async def test_global_filter_allow_emoji_with_text(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'allow_emoji': False
    }
    # Contains text, should NOT be blocked by emoji filter
    mock_context.event.message.message = "Good 🦸‍♂️"
    result = await global_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_global_filter_block_emoji_with_spaces(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'allow_emoji': False
    }
    mock_context.event.message.message = "  😀  😂  "
    result = await global_filter._process(mock_context)
    assert result is False

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
@pytest.mark.asyncio
async def test_global_filter_extension_blacklist(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_extension_enabled': True,
        'media_extensions': ['exe', 'bat'],
        'extension_filter_mode': 'blacklist'
    }
    
    mock_media = MagicMock()
    mock_media.photo = None
    mock_media.voice = None
    mock_media.audio = None
    mock_media.video = None
    
    attr = MagicMock()
    attr.file_name = "test.exe"
    mock_doc = MagicMock()
    mock_doc.attributes = [attr]
    mock_media.document = mock_doc
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_extension_whitelist(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_extension_enabled': True,
        'media_extensions': ['jpg', 'png'],
        'extension_filter_mode': 'whitelist'
    }
    
    mock_media = MagicMock()
    mock_media.photo = None
    mock_media.voice = None
    mock_media.audio = None
    mock_media.video = None
    
    attr = MagicMock()
    attr.file_name = "secret.pdf"
    mock_doc = MagicMock()
    mock_doc.attributes = [attr]
    mock_media.document = mock_doc
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_size_limit(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_size_filter_enabled': True,
        'media_size_limit': 5 # 5MB
    }
    
    mock_media = MagicMock()
    # Trigger media loop
    mock_media.photo = True 
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    with patch("core.helpers.media.get_media_size", new_callable=AsyncMock) as mock_size:
        mock_size.return_value = 10 * 1024 * 1024 # 10MB
        result = await global_filter._process(mock_context)
        assert result is True
        assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_duration_min(global_filter, mock_context, mock_forward_manager):
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_duration_enabled': True,
        'duration_min_seconds': 30
    }
    
    mock_media = MagicMock()
    mock_media.video = MagicMock()
    mock_media.video.duration = 10 
    mock_media.photo = None
    mock_media.voice = None
    mock_media.audio = None
    mock_media.document = None
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = ""
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is False

@pytest.mark.asyncio
async def test_global_filter_message_with_blocked_media(global_filter, mock_context, mock_forward_manager):
    # Test line 291-294 logic
    mock_forward_manager.get_global_media_settings.return_value = {
        'allow_text': True,
        'media_types': {'image': False}
    }
    
    mock_media = MagicMock()
    mock_media.photo = True
    mock_media.video = None
    mock_media.audio = None
    mock_media.voice = None
    mock_media.document = None
    
    mock_context.event.message.media = mock_media
    mock_context.event.message.message = "This text should be forwarded"
    
    result = await global_filter._process(mock_context)
    assert result is True
    assert mock_context.should_forward is True # Media blocked, but text allowed
    assert mock_context.media_blocked is True
