import pytest
from unittest.mock import MagicMock, patch
from filters.info_filter import InfoFilter
from types import SimpleNamespace
from datetime import datetime, timezone

@pytest.fixture
def info_filter():
    return InfoFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.is_original_link = False
    context.rule.is_original_sender = False
    context.rule.is_original_time = False
    
    context.event = MagicMock()
    context.event.chat_id = -1001234567890
    context.event.message = MagicMock()
    context.event.message.id = 100
    context.event.message.date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    context.event.sender = None
    
    context.original_link = ""
    context.sender_info = ""
    context.time_info = ""
    return context

@pytest.mark.asyncio
async def test_info_filter_link_default(info_filter, mock_context):
    mock_context.rule.is_original_link = True
    result = await info_filter._process(mock_context)
    assert result is True
    assert "t.me/c/1234567890/100" in mock_context.original_link

@pytest.mark.asyncio
async def test_info_filter_link_template(info_filter, mock_context):
    mock_context.rule.is_original_link = True
    mock_context.rule.original_link_template = "Source: {original_link}"
    result = await info_filter._process(mock_context)
    assert result is True
    assert "Source: https://t.me/c/1234567890/100" in mock_context.original_link

@pytest.mark.asyncio
async def test_info_filter_sender_user(info_filter, mock_context):
    mock_context.rule.is_original_sender = True
    mock_context.event.message.sender_chat = None # Important
    
    mock_sender = MagicMock(spec=['id', 'first_name', 'last_name'])
    mock_sender.id = 555
    mock_sender.first_name = "John"
    mock_sender.last_name = "Doe"
    mock_context.event.sender = mock_sender
    
    result = await info_filter._process(mock_context)
    assert result is True
    assert "John Doe" in mock_context.sender_info
    assert mock_context.sender_id == 555
    assert mock_context.sender_name == "John Doe"

@pytest.mark.asyncio
async def test_info_filter_sender_chat(info_filter, mock_context):
    mock_context.rule.is_original_sender = True
    
    mock_chat = MagicMock()
    mock_chat.id = -100999
    mock_chat.title = "Awesome Channel"
    mock_context.event.message.sender_chat = mock_chat
    mock_context.event.sender = None
    
    result = await info_filter._process(mock_context)
    assert result is True
    assert "Awesome Channel" in mock_context.sender_info
    assert mock_context.sender_id == -100999

@pytest.mark.asyncio
async def test_info_filter_time_default(info_filter, mock_context):
    mock_context.rule.is_original_time = True
    
    with patch("core.config.settings.TIMEZONE", "UTC"):
        result = await info_filter._process(mock_context)
        assert result is True
        assert "2023-01-01 12:00:00" in mock_context.time_info
