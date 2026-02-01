import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.delay_filter import DelayFilter, RescheduleTaskException
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

@pytest.fixture
def delay_filter():
    return DelayFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.id = 1
    context.rule.enable_delay = True
    context.rule.delay_seconds = 10
    
    context.event = MagicMock()
    context.event.message = MagicMock()
    # Telethon message.date is aware datetime in UTC
    context.event.message.date = datetime.now(timezone.utc)
    
    context.message_obj = MagicMock()
    context.message_obj.id = 123
    context.message_obj.text = "old text"
    
    context.chat_id = -1001234567890
    context.client = AsyncMock()
    context.message_text = "old text"
    return context

@pytest.mark.asyncio
async def test_delay_filter_skip_if_disabled(delay_filter, mock_context):
    mock_context.rule.enable_delay = False
    result = await delay_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_delay_filter_reschedule(delay_filter, mock_context):
    # Message just arrived (age ~ 0)
    mock_context.event.message.date = datetime.now(timezone.utc)
    
    with pytest.raises(RescheduleTaskException) as excinfo:
        await delay_filter._process(mock_context)
    
    assert excinfo.value.delay_seconds <= 10
    assert excinfo.value.delay_seconds > 0

@pytest.mark.asyncio
async def test_delay_filter_refresh_success(delay_filter, mock_context):
    # Message is 20s old
    mock_context.event.message.date = datetime.now(timezone.utc) - timedelta(seconds=20)
    
    mock_updated = MagicMock()
    mock_updated.text = "new text"
    mock_updated.grouped_id = None
    mock_context.client.get_messages.return_value = mock_updated
    
    result = await delay_filter._process(mock_context)
    
    assert result is True
    assert mock_context.message_obj.text == "new text"
    assert mock_context.message_text == "new text"
    assert mock_context.event.message == mock_updated

@pytest.mark.asyncio
async def test_delay_filter_refresh_no_message(delay_filter, mock_context):
    mock_context.event.message.date = datetime.now(timezone.utc) - timedelta(seconds=20)
    mock_context.client.get_messages.return_value = None
    
    result = await delay_filter._process(mock_context)
    assert result is True # Should continue with original message
