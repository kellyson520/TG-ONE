import pytest
from unittest.mock import AsyncMock, MagicMock
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
    mock_context.event.message.photo = None
    mock_context.event.message.document = None
    
    result = await init_filter._process(mock_context)
    assert result is True
    assert hasattr(mock_context, 'dup_signatures')

@pytest.mark.asyncio
async def test_init_filter_photo_sig(init_filter, mock_context):
    mock_photo = MagicMock()
    mock_size = MagicMock()
    mock_size.size = 1024
    mock_size.w = 800
    mock_size.h = 600
    mock_photo.sizes = [mock_size]
    mock_context.event.message.photo = mock_photo
    
    await init_filter._process(mock_context)
    assert len(mock_context.dup_signatures) == 1
    assert "photo:800x600:1024" in mock_context.dup_signatures[0][0]

@pytest.mark.asyncio
async def test_init_filter_media_group_text(init_filter, mock_context):
    mock_context.event.message.grouped_id = 123456
    
    # Mock iter_messages
    mock_msg = MagicMock()
    mock_msg.grouped_id = 123456
    mock_msg.text = "group caption"
    
    # Custom async iterator
    class AsyncIter:
        def __init__(self, items):
            self.items = items
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    # Use MagicMock for the method itself to return the iterator directly
    mock_context.event.client.iter_messages = MagicMock(return_value=AsyncIter([mock_msg]))
    
    await init_filter._process(mock_context)
    assert mock_context.message_text == "group caption"

@pytest.mark.asyncio
async def test_init_filter_video_sig(init_filter, mock_context):
    mock_doc = MagicMock()
    mock_doc.mime_type = "video/mp4"
    mock_doc.size = 2048
    
    video_attr = DocumentAttributeVideo(duration=10, w=1920, h=1080)
    mock_doc.attributes = [video_attr]
    mock_context.event.message.photo = None
    mock_context.event.message.document = mock_doc
    
    await init_filter._process(mock_context)
    assert len(mock_context.dup_signatures) == 1
    assert "video:10s:1920x1080:2048" in mock_context.dup_signatures[0][0]

@pytest.mark.asyncio
async def test_init_filter_document_sig(init_filter, mock_context):
    mock_doc = MagicMock()
    mock_doc.mime_type = "application/pdf"
    mock_doc.size = 5000
    
    file_attr = MagicMock()
    file_attr.__class__.__name__ = "DocumentAttributeFilename"
    file_attr.file_name = "test.pdf"
    mock_doc.attributes = [file_attr]
    mock_context.event.message.photo = None
    mock_context.event.message.document = mock_doc
    
    await init_filter._process(mock_context)
    assert len(mock_context.dup_signatures) == 1
    assert "document:application/pdf:5000:test.pdf" in mock_context.dup_signatures[0][0]

@pytest.mark.asyncio
async def test_init_filter_iter_messages_error(init_filter, mock_context):
    mock_context.event.message.grouped_id = 123456
    mock_context.event.client.iter_messages.side_effect = Exception("iter error")
    
    result = await init_filter._process(mock_context)
    assert result is True
    assert any("收集媒体组消息错误" in e for e in mock_context.errors)

@pytest.mark.asyncio
async def test_init_filter_single_photo_sig(init_filter, mock_context):
    mock_context.event.message.grouped_id = None
    mock_photo = MagicMock()
    mock_size = MagicMock()
    mock_size.w = 800
    mock_size.h = 600
    mock_size.size = 50000
    mock_photo.sizes = [mock_size]
    mock_context.event.message.photo = mock_photo
    
    await init_filter._process(mock_context)
    assert len(mock_context.dup_signatures) == 1
    assert "photo:800x600:50000" in mock_context.dup_signatures[0][0]

@pytest.mark.asyncio
async def test_init_filter_single_doc_sig(init_filter, mock_context):
    mock_context.event.message.grouped_id = None
    mock_doc = MagicMock()
    mock_doc.mime_type = "application/pdf"
    mock_doc.size = 123456
    attr = MagicMock()
    attr.file_name = "test.pdf"
    mock_doc.attributes = [attr]
    mock_context.event.message.photo = None
    mock_context.event.message.document = mock_doc
    
    await init_filter._process(mock_context)
    assert len(mock_context.dup_signatures) == 1
    assert "document:application/pdf:123456:test.pdf" in mock_context.dup_signatures[0][0]

@pytest.mark.asyncio
async def test_init_filter_error_in_sig(init_filter, mock_context):
    # Trigger Exception in signature generation
    # We want to hit line 162: except Exception: sig = None
    mock_context.event.message.photo = MagicMock()
    # Setting an attribute to a non-iterable to cause error in 'for s in sizes'
    mock_context.event.message.photo.sizes = 123 
    
    await init_filter._process(mock_context)
    # Should not crash, and should not add signature for this message
    assert mock_context.dup_signatures == []
