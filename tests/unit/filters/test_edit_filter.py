import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from filters.edit_filter import EditFilter
from enums.enums import HandleMode, PreviewMode, MessageMode
from telethon.tl.types import Channel
from types import SimpleNamespace

@pytest.fixture
def edit_filter():
    return EditFilter()

@pytest.fixture
def mock_context():
    context = SimpleNamespace()
    context.rule = SimpleNamespace()
    context.rule.handle_mode = HandleMode.EDIT
    context.rule.is_preview = PreviewMode.OFF
    context.rule.message_mode = MessageMode.HTML
    
    context.event = MagicMock()
    context.event.message = MagicMock()
    context.event.message.id = 123
    context.event.message.text = "old text"
    context.event.message.media = None
    context.event.chat_id = -100123
    context.event.get_chat = AsyncMock()
    
    context.sender_info = "Sender: "
    context.message_text = "Message"
    context.time_info = " Time"
    context.original_link = " Link"
    
    context.is_media_group = False
    context.client = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_edit_filter_skip_not_edit(edit_filter, mock_context):
    mock_context.rule.handle_mode = HandleMode.FORWARD
    result = await edit_filter._process(mock_context)
    assert result is True

@pytest.mark.asyncio
async def test_edit_filter_not_channel(edit_filter, mock_context):
    mock_chat = MagicMock() # Not a Channel instance
    mock_chat.id = 123
    mock_context.event.get_chat.return_value = mock_chat
    
    result = await edit_filter._process(mock_context)
    assert result is False

@pytest.mark.asyncio
async def test_edit_filter_success(edit_filter, mock_context):
    mock_chat = MagicMock(spec=Channel)
    mock_chat.id = 123
    mock_context.event.get_chat.return_value = mock_chat
    
    mock_main = MagicMock()
    mock_main.user_client = AsyncMock()
    
    with patch("filters.edit_filter.get_main_module", return_value=mock_main):
        result = await edit_filter._process(mock_context)
        
        assert result is False # Returns False as it stops processing
        mock_main.user_client.edit_message.assert_called_once()
        args, kwargs = mock_main.user_client.edit_message.call_args
        assert kwargs['text'] == "Sender: Message Time Link"
        assert kwargs['link_preview'] is False

@pytest.mark.asyncio
async def test_edit_filter_no_text_change(edit_filter, mock_context):
    mock_chat = MagicMock(spec=Channel)
    mock_chat.id = 123
    mock_context.event.get_chat.return_value = mock_chat
    
    mock_context.event.message.text = "Sender: Message Time Link"
    
    mock_main = MagicMock()
    mock_main.user_client = AsyncMock()
    
    with patch("filters.edit_filter.get_main_module", return_value=mock_main):
        result = await edit_filter._process(mock_context)
        assert result is False
        mock_main.user_client.edit_message.assert_not_called()
