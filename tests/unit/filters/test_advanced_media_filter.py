import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.advanced_media_filter import AdvancedMediaFilter
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio, DocumentAttributeAnimated
from types import SimpleNamespace

@pytest.fixture
def adv_media_filter():
    return AdvancedMediaFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.enable_duration_filter = False
    context.rule.enable_resolution_filter = False
    context.rule.enable_file_size_range = False
    
    context.event = MagicMock()
    context.event.message = MagicMock()
    context.event.message.media = None
    
    return context

@pytest.mark.asyncio
async def test_adv_media_filter_no_media(adv_media_filter, mock_context):
    result = await adv_media_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_adv_media_filter_duration_pass(adv_media_filter, mock_context):
    mock_context.rule.enable_duration_filter = True
    mock_context.rule.min_duration = 5
    mock_context.rule.max_duration = 60
    
    # Mock video media
    mock_context.event.message.media = MagicMock()
    mock_doc = MagicMock()
    attr_video = DocumentAttributeVideo(duration=30, w=1920, h=1080)
    mock_doc.attributes = [attr_video]
    mock_context.event.message.media.document = mock_doc
    
    result = await adv_media_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_adv_media_filter_duration_fail(adv_media_filter, mock_context):
    mock_context.rule.enable_duration_filter = True
    mock_context.rule.min_duration = 60
    mock_context.rule.max_duration = 0
    
    # Mock voice
    mock_context.event.message.media = MagicMock(spec=['voice', 'document', 'audio', 'video', 'photo'])
    mock_context.event.message.media.document = None
    mock_context.event.message.media.audio = None
    mock_context.event.message.media.video = None
    mock_context.event.message.media.photo = None
    
    mock_voice = MagicMock()
    mock_voice.duration = 30
    mock_context.event.message.media.voice = mock_voice
    
    result = await adv_media_filter._process(mock_context)
    assert result is False

@pytest.mark.asyncio
async def test_adv_media_filter_resolution_pass(adv_media_filter, mock_context):
    mock_context.rule.enable_resolution_filter = True
    mock_context.rule.min_width = 100
    mock_context.rule.max_width = 2000
    mock_context.rule.min_height = 100
    mock_context.rule.max_height = 2000
    
    # Mock photo
    mock_context.event.message.media = MagicMock()
    mock_context.event.message.media.document = None
    mock_photo = MagicMock()
    mock_size = MagicMock()
    mock_size.size = 1000
    mock_size.w = 1280
    mock_size.h = 720
    mock_photo.sizes = [mock_size]
    mock_context.event.message.media.photo = mock_photo
    
    result = await adv_media_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_adv_media_filter_size_range_fail(adv_media_filter, mock_context):
    mock_context.rule.enable_file_size_range = True
    mock_context.rule.min_file_size = 1000 # 1000KB = 1MB
    mock_context.rule.max_file_size = 5000 # 5000KB = 5MB
    
    mock_context.event.message.media = MagicMock()
    
    # get_media_size returns MB
    with patch("filters.advanced_media_filter.get_media_size", new_callable=AsyncMock) as mock_get_size:
        mock_get_size.return_value = 0.5 # 0.5MB = 512KB
        
        result = await adv_media_filter._process(mock_context)
        assert result is False
