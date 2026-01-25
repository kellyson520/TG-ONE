import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.event_bus import EventBus
from services.notification_service import NotificationService
from core.config import settings

@pytest.mark.asyncio
async def test_notification_flow():
    """Test that events trigger admin notifications"""
    
    # Setup Mocks
    mock_bot = AsyncMock()
    bus = EventBus()
    
    # Inject Mock Admin IDs
    with patch.object(settings, 'ADMIN_IDS', [123456, 789012]):
        service = NotificationService(mock_bot, bus)
        
        # Test 1: System Error Event
        error_data = {"module": "TestModule", "error": "Something exploded"}
        await bus.publish("ERROR_SYSTEM", error_data)
        
        # Allow async tasks to run
        await asyncio.sleep(0.1)
        
        # Verify
        assert mock_bot.send_message.call_count == 2 # 2 admins
        call_args = mock_bot.send_message.call_args_list
        # Check first admin call
        assert call_args[0][0][0] == 123456
        assert "Something exploded" in call_args[0][0][1]
        assert "TestModule" in call_args[0][0][1]
        assert "🚨" in call_args[0][0][1] # Error Icon

        # Test 2: System Alert Event
        mock_bot.reset_mock()
        alert_data = {"message": "High CPU Usage"}
        await bus.publish("SYSTEM_ALERT", alert_data)
        await asyncio.sleep(0.1)
        
        assert mock_bot.send_message.call_count == 2
        assert "High CPU Usage" in mock_bot.send_message.call_args[0][1]
        assert "⚠️" in mock_bot.send_message.call_args[0][1] # Warning Icon
