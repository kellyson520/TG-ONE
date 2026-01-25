
import pytest
from unittest.mock import AsyncMock, patch
from handlers.command_handlers import handle_db_optimize_command, handle_logs_command

@pytest.mark.asyncio
async def test_db_optimize_command():
    # Mock event
    event = AsyncMock()
    event.client = AsyncMock()
    event.chat_id = 12345
    event.sender_id = 98765
    event.message.id = 67890
    event.message.to_dict.return_value = {}  # Prevent JSON issues
    event.to_dict.return_value = {}
    
    # Mock progress message
    progress_msg = AsyncMock()
    event.reply.return_value = progress_msg
    
    # Mock models functions
    with patch("models.models.analyze_database", return_value=True), \
         patch("models.models.vacuum_database", return_value=True), \
         patch("models.models.cleanup_old_logs", return_value=100), \
         patch("handlers.command_handlers.async_delete_user_message", new_callable=AsyncMock) as mock_delete, \
         patch("handlers.command_handlers.reply_and_delete", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock):
         
        await handle_db_optimize_command(event)
        
        # Verify calls
        event.reply.assert_called_once()
        progress_msg.edit.assert_called()
        assert "优化完成" in progress_msg.edit.call_args[0][0]

@pytest.mark.asyncio
async def test_logs_command():
    event = AsyncMock()
    event.client = AsyncMock()
    event.chat_id = 12345
    event.sender_id = 98765
    event.message.id = 67890
    event.message.text = "/logs 10"
    event.message.to_dict.return_value = {}
    event.to_dict.return_value = {}
    
    # Configure reply message to avoid AsyncMock JSON serialization error
    mock_reply_msg = AsyncMock()
    mock_reply_msg.chat_id = 12345
    mock_reply_msg.id = 99999
    event.reply.return_value = mock_reply_msg
    
    with patch("services.system_service.system_service.get_logs", return_value="Log content"):
        await handle_logs_command(event, ["/logs", "10"])
        
        event.client.delete_messages.assert_not_called() # Should use async_delete_user_message
        
