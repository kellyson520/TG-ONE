import pytest
from unittest.mock import MagicMock, AsyncMock, patch
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

    @pytest.fixture(autouse=True)
    def mock_audit_service(self):
        # Patch audit_service in core.aop to prevent real calls during tests
        with patch("services.audit_service.audit_service") as mock_audit:
            mock_audit.log_event = AsyncMock()
            yield mock_audit

    async def test_is_admin_env(self, user_service, monkeypatch):
        # 1. Test ADMINS in settings
        with patch("core.config.settings.ADMIN_IDS", [123, 456]):
             # We also need to patch get_admin_list logic if it reads settings directly, which it does.
             # Wait, get_admin_list in common.py reads settings.
             # So patching settings.ADMIN_IDS should be enough if settings is imported in common.py
             
             assert await user_service.is_admin(123) is True
             assert await user_service.is_admin(456) is True
             assert await user_service.is_admin(789) is False

    async def test_is_admin_db(self, user_service, monkeypatch):
        # 2. Test DB admin
        with patch("core.config.settings.ADMIN_IDS", [123]):
            
            async def mock_get_admin(tid):
                if str(tid) == "456":
                    # Return a simple truthy object (Mock or dict)
                    return MagicMock(id=1, username="admin") 
                return None

            # Mock repo to return an admin for 456
            user_service.container.user_repo.get_admin_by_telegram_id = AsyncMock(side_effect=mock_get_admin)
            
            assert await user_service.is_admin(123) is True  # Settings hit
            assert await user_service.is_admin(456) is True  # DB hit
            assert await user_service.is_admin(789) is False # Miss

    async def test_is_admin_channel(self, user_service, monkeypatch):
        # 3. Test Channel Admin logic
        with patch("core.config.settings.ADMIN_IDS", [123]): # Bot Admin ID is 123
            
            mock_event = MagicMock()
            mock_event.chat_id = -100999
            mock_event.message.is_channel = True
            mock_event.message.is_group = False
            
            # User 456 is a random user (not in env, not in db)
            user_service.container.user_repo.get_admin_by_telegram_id = AsyncMock(return_value=None)
            
            # Mock get_channel_admins helper
            mock_get_admins = AsyncMock(return_value=[123, 999])
            monkeypatch.setattr("core.helpers.common.get_channel_admins", mock_get_admins)
            
            # Request from user 456
            assert await user_service.is_admin(456, event=mock_event) is True
            
            # If bot owner is NOT admin of the channel
            mock_get_admins.return_value = [999]
            assert await user_service.is_admin(456, event=mock_event) is False

    async def test_update_user(self, user_service, mock_audit_service):
        # Setup
        user_service.container.user_repo.update_user = AsyncMock(return_value=True)
        
        # Execute
        result = await user_service.update_user(user_id=100, is_admin=True)
        
        # Verify Repo Call
        user_service.container.user_repo.update_user.assert_called_once_with(100, is_admin=True)
        assert result is True
        
        # Verify Audit Log (Async task - wait briefly)
        import asyncio
        await asyncio.sleep(0.01)
        
        mock_audit_service.log_event.assert_called()
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["action"] == "UPDATE_USER"
        assert call_kwargs["resource_id"] == "100"

    async def test_delete_user(self, user_service, mock_audit_service):
        # Setup
        user_service.container.user_repo.delete_user = AsyncMock(return_value=True)
        
        # Execute
        result = await user_service.delete_user(user_id=200)
        
        # Verify Repo Call
        user_service.container.user_repo.delete_user.assert_called_once_with(200)
        assert result is True
        
        # Verify Audit Log
        import asyncio
        await asyncio.sleep(0.01)
        
        mock_audit_service.log_event.assert_called()
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["action"] == "DELETE_USER"
        assert call_kwargs["resource_id"] == "200"
