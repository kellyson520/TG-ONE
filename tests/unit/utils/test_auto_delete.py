"""
Unit tests for auto-delete utilities.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from utils.processing.auto_delete import reply_and_delete, respond_and_delete, send_message_and_delete

@pytest.mark.asyncio
class TestAutoDeleteTools:
    
    async def test_reply_and_delete_basic(self):
        event = AsyncMock()
        mock_msg = MagicMock()
        event.reply.return_value = mock_msg
        
        with patch("services.task_service.message_task_manager.schedule_delete", new_callable=AsyncMock) as mock_sched:
            await reply_and_delete(event, "Test text", 5)
            
            event.reply.assert_called_with("Test text")
            mock_sched.assert_called_once_with(mock_msg, 5)

    async def test_respond_and_delete_basic(self):
        event = AsyncMock()
        mock_msg = MagicMock()
        event.respond.return_value = mock_msg
        
        with patch("services.task_service.message_task_manager.schedule_delete", new_callable=AsyncMock) as mock_sched:
            await respond_and_delete(event, "Test text", 10)
            
            event.respond.assert_called_with("Test text")
            mock_sched.assert_called_once_with(mock_msg, 10)

    async def test_send_message_and_delete_basic(self):
        client = AsyncMock()
        mock_msg = MagicMock()
        client.send_message.return_value = mock_msg
        
        with patch("services.task_service.message_task_manager.schedule_delete", new_callable=AsyncMock) as mock_sched:
            await send_message_and_delete(client, -1001, "Hello", 0)
            
            client.send_message.assert_called_with(-1001, "Hello")
            mock_sched.assert_called_once_with(mock_msg, 0)

    async def test_no_deletion_when_neg_one(self):
        event = AsyncMock()
        event.reply.return_value = MagicMock()
        
        with patch("services.task_service.message_task_manager.schedule_delete", new_callable=AsyncMock) as mock_sched:
            await reply_and_delete(event, "Keep forever", -1)
            
            mock_sched.assert_not_called()
