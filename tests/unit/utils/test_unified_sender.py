import pytest
from unittest.mock import AsyncMock, MagicMock
from utils.unified_sender import UnifiedSender

@pytest.mark.asyncio
async def test_unified_sender_text():
    mock_client = AsyncMock()
    sender = UnifiedSender(mock_client)
    
    await sender.send(12345, text="Hello")
    mock_client.send_message.assert_called_with(12345, "Hello")
    mock_client.send_file.assert_not_called()

@pytest.mark.asyncio
async def test_unified_sender_media():
    mock_client = AsyncMock()
    sender = UnifiedSender(mock_client)
    mock_media = MagicMock()
    
    await sender.send(12345, text="Caption", media=mock_media)
    mock_client.send_file.assert_called_with(12345, mock_media, caption="Caption")
    mock_client.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_unified_sender_album_with_buttons():
    mock_client = AsyncMock()
    sender = UnifiedSender(mock_client)
    mock_media_list = [MagicMock(), MagicMock()]
    buttons = [[MagicMock()]]
    
    await sender.send(12345, media=mock_media_list, buttons=buttons)
    
    # Should call send_file for album with buttons removed
    mock_client.send_file.assert_called()
    args, kwargs = mock_client.send_file.call_args
    assert args[0] == 12345
    assert args[1] == mock_media_list
    assert 'buttons' not in kwargs 
    
    # Should call send_message for buttons
    mock_client.send_message.assert_called()
    args_msg, kwargs_msg = mock_client.send_message.call_args
    assert args_msg[0] == 12345
    assert args_msg[1] == "👇 互动按钮"
    assert kwargs_msg['buttons'] == buttons

@pytest.mark.asyncio
async def test_unified_sender_forbidden_kwargs():
    mock_client = AsyncMock()
    sender = UnifiedSender(mock_client)
    
    # Passing arbitrary kwargs that are not in whitelist should be filtered
    await sender.send(12345, text="Hello", unsafe_kwarg="should_be_removed")
    
    mock_client.send_message.assert_called()
    _, kwargs = mock_client.send_message.call_args
    assert 'unsafe_kwarg' not in kwargs

@pytest.mark.asyncio
async def test_unified_sender_mixed_kwargs():
    mock_client = AsyncMock()
    sender = UnifiedSender(mock_client)
    
    # Valid kwargs should pass
    await sender.send(12345, text="Hello", reply_to=111, silent=True)
    
    mock_client.send_message.assert_called()
    _, kwargs = mock_client.send_message.call_args
    assert kwargs['reply_to'] == 111
    assert kwargs['silent'] is True
