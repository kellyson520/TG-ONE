import pytest
from unittest.mock import AsyncMock, MagicMock
from filters.reply_filter import ReplyFilter
from types import SimpleNamespace

@pytest.fixture
def reply_filter():
    return ReplyFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.enable_comment_button = True
    context.rule.target_chat = SimpleNamespace(telegram_chat_id="123456")
    
    context.is_media_group = True
    context.comment_link = "https://t.me/c/1/2"
    context.forwarded_messages = [MagicMock(id=999)]
    
    context.client = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_reply_filter_skip_if_not_enabled(reply_filter, mock_context):
    mock_context.rule.enable_comment_button = False
    result = await reply_filter._process(mock_context)
    assert result is True
    mock_context.client.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_reply_filter_skip_if_not_media_group(reply_filter, mock_context):
    mock_context.is_media_group = False
    result = await reply_filter._process(mock_context)
    assert result is True
    mock_context.client.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_reply_filter_send_reply(reply_filter, mock_context):
    result = await reply_filter._process(mock_context)
    assert result is True
    mock_context.client.send_message.assert_called_once()
    args, kwargs = mock_context.client.send_message.call_args
    assert kwargs['reply_to'] == 999
    assert kwargs['entity'] == 123456
