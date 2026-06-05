
import pytest
from unittest.mock import AsyncMock, patch
from handlers.command_handlers import handle_db_optimize_command, handle_logs_command

@pytest.mark.asyncio
async def test_db_optimize_command():
    # Mock event
    event = AsyncMock()
    event.client = AsyncMock()
    event.chat_id = 12345
    event.message.id = 67890
    
    # Mock progress message (respond returns it)
    progress_msg = AsyncMock()
    event.respond.return_value = progress_msg
    
    # Mock service
    with patch("services.db_maintenance_service.db_maintenance_service.optimize_database", new_callable=AsyncMock) as mock_opt, \
         patch("handlers.commands.system_commands.async_delete_user_message", new_callable=AsyncMock):
         
        mock_opt.return_value = {"success": True, "message": "Done"}
        
        await handle_db_optimize_command(event)
        
        # Verify calls
        event.respond.assert_called()
        progress_msg.edit.assert_called()
        assert "优化完成" in progress_msg.edit.call_args[0][0]

@pytest.mark.asyncio
async def test_logs_command():
    event = AsyncMock()
    event.message.text = "/logs 10"
    
    with patch("handlers.commands.system_commands.reply_and_delete", new_callable=AsyncMock) as mock_rd:
        await handle_logs_command(event, ["/logs", "10"])
        mock_rd.assert_called_once()
        assert "pending migration" in mock_rd.call_args[0][1]
