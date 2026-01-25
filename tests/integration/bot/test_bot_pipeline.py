import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telethon import events

class TestBotPipeline:
    
    @pytest.mark.asyncio
    @patch("handlers.bot_handler.is_admin", new_callable=AsyncMock)
    @patch("handlers.bot_handler.get_user_id", new_callable=AsyncMock)
    async def test_start_command(self, mock_get_user_id, mock_is_admin):
        """Test the /start command flow via handle_command."""
        from handlers.bot_handler import handle_command
        
        # Setup Mocks
        mock_is_admin.return_value = True
        mock_get_user_id.return_value = 123456789
        
        # Mock Client
        client = AsyncMock()
        
        # Mock Event
        event = AsyncMock() # Removed spec to allow dynamic attributes like respond/reply
        event.message = MagicMock()
        event.message.text = "/start"
        event.sender_id = 123456789
        event.chat_id = 123456789
        event.get_chat.return_value.id = 123456789
        
        # Mock the specific handler that start calls
        with patch("handlers.bot_handler.handle_start_command", new_callable=AsyncMock) as mock_start:
            await handle_command(client, event)
            mock_start.assert_called_once()


    @pytest.mark.asyncio
    @patch("handlers.bot_handler.is_admin", new_callable=AsyncMock)
    async def test_menu_navigation(self, mock_is_admin):
        """Test menu callback clicks."""
        from handlers.bot_handler import callback_handler
        
        mock_is_admin.return_value = True
        
        event = AsyncMock() # Removed spec
        event.data = b"menu_main"
        event.sender_id = 123456789
        
        with patch("handlers.bot_handler.handle_callback", new_callable=AsyncMock) as mock_cb:
            await callback_handler(event)
            mock_cb.assert_called_once_with(event)

    @pytest.mark.asyncio
    @patch("handlers.bot_handler.is_admin", new_callable=AsyncMock)
    async def test_unknown_command(self, mock_is_admin):
        """Test exception handling or unknown command."""
        from handlers.bot_handler import handle_command
        
        mock_is_admin.return_value = True
        
        client = AsyncMock()
        event = AsyncMock() # Removed spec
        # Explicitly setup message mock object
        mock_msg = MagicMock()
        mock_msg.text = "/unknown_command_123"
        event.message = mock_msg
        
        event.sender_id = 123456789
        event.chat_id = 123456789
        event.get_chat.return_value.id = 123456789
        
        # Simply ensure it calls respond and doesn't crash
        await handle_command(client, event)
        event.respond.assert_called() # Should respond with unknown command message
