import pytest
from unittest.mock import MagicMock, AsyncMock
from services.user_service import UserService
from schemas.user import UserDTO

@pytest.mark.asyncio
class TestUserService:
    @pytest.fixture
    def user_service(self):
        service = UserService()
        # Mock container
        service.container.user_repo = MagicMock()
        service.container.user_client = AsyncMock()
        return service

    async def test_is_admin_env(self, user_service, monkeypatch):
        # 1. Test ADMINS in env
        monkeypatch.setenv("ADMINS", "123,456")
        assert await user_service.is_admin(123) is True
        assert await user_service.is_admin(456) is True
        assert await user_service.is_admin(789) is False

    async def test_is_admin_db(self, user_service, monkeypatch):
        # 2. Test DB admin
        monkeypatch.setenv("ADMINS", "123")
        
        # Mock repo to return an admin for 456
        user_service.container.user_repo.get_admin_by_telegram_id = AsyncMock(
            side_effect=lambda tid: UserDTO(id=1, telegram_id=tid, username="admin", is_admin=True) if tid == "456" else None
        )
        
        assert await user_service.is_admin(123) is True  # Env hit
        assert await user_service.is_admin(456) is True  # DB hit
        assert await user_service.is_admin(789) is False # Miss

    async def test_is_admin_channel(self, user_service, monkeypatch):
        # 3. Test Channel Admin logic
        monkeypatch.setenv("ADMINS", "123") # Bot Admin ID is 123
        
        mock_event = MagicMock()
        mock_event.chat_id = -100999
        mock_event.message.is_channel = True
        mock_event.message.is_group = False
        
        # User 456 is a random user (not in env, not in db)
        user_service.container.user_repo.get_admin_by_telegram_id = AsyncMock(return_value=None)
        
        # Mock get_channel_admins helper
        # If bot admin (123) is in channel admins, any user in the channel can't be admin based on this logic?
        # WAIT: The logic I implemented in user_service was:
        # if bot_admins (from env) intersects channel_admins, return True.
        # This means if the BOT'S OWNER is an admin of the channel, we treat the request in that channel as authorized?
        # Actually, common.is_admin logic was:
        # admin_in_channel = any(admin_id in channel_admins for admin_id in bot_admins)
        # if admin_in_channel: return True
        # This is the "Bot is authorized in this channel" logic.
        
        mock_get_admins = AsyncMock(return_value=[123, 999])
        monkeypatch.setattr("utils.helpers.common.get_channel_admins", mock_get_admins)
        
        # Request from user 456 (not admin himself, but bot owner 123 is admin of the channel)
        assert await user_service.is_admin(456, event=mock_event) is True
        
        # If bot owner is NOT admin of the channel
        mock_get_admins.return_value = [999]
        assert await user_service.is_admin(456, event=mock_event) is False
