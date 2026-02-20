import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.authentication_service import AuthenticationService
from models.models import ActiveSession

@pytest.fixture
def auth_service():
    return AuthenticationService()

@pytest.mark.asyncio
async def test_create_session_success(auth_service):
    user_id = 1
    ip = "127.0.0.1"
    ua = "TestAgent"
    
    with patch("core.container.container") as mock_container:
        # Mock DB Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.delete = MagicMock()
        
        # Mock context manager behavior for db.get_session()
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_container.db.get_session.return_value = context_manager
        
        # Mock existing sessions (empty)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Call method
        access, refresh = await auth_service.create_session(user_id, ip, ua)
        
        # Verify tokens returned
        assert isinstance(access, str)
        assert len(access) > 0
        assert isinstance(refresh, str)
        assert len(refresh) > 0
        
        # Verify DB calls
        # 1. Select existing
        mock_session.execute.assert_called_once()
        # 2. Add new session
        mock_session.add.assert_called_once()
        new_session = mock_session.add.call_args[0][0]
        assert isinstance(new_session, ActiveSession)
        assert new_session.user_id == user_id
        assert new_session.ip_address == ip
        # 3. Commit
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_create_session_max_limit_enforced(auth_service):
    user_id = 1
    ip = "127.0.0.1"
    ua = "TestAgent"
    MAX_SESSIONS = 5
    
    with patch("core.container.container") as mock_container, \
         patch("services.authentication_service.settings.MAX_ACTIVE_SESSIONS", MAX_SESSIONS):
        # Mock DB Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.delete = MagicMock()
        
        # Mock context manager behavior for db.get_session()
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_container.db.get_session.return_value = context_manager
        
        # Mock 5 existing sessions
        existing_sessions = [MagicMock(spec=ActiveSession, id=i) for i in range(5)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = existing_sessions
        mock_session.execute.return_value = mock_result

        # Call method
        await auth_service.create_session(user_id, ip, ua)
        
        # Verify deletion
        mock_session.delete.assert_called_once_with(existing_sessions[0])
        
        # Verify addition
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_session_cleanup_multiple(auth_service):
    """Test if user somehow has way more sessions (e.g. 10), it cleans up to limit."""
    user_id = 1
    MAX_SESSIONS = 5
    EXISTING_COUNT = 10
    
    with patch("core.container.container") as mock_container, \
         patch("services.authentication_service.settings.MAX_ACTIVE_SESSIONS", MAX_SESSIONS):
        # Mock DB Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.delete = MagicMock()
        
        # Mock context manager behavior for db.get_session()
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_container.db.get_session.return_value = context_manager
        
        existing_sessions = [MagicMock(spec=ActiveSession, id=i) for i in range(EXISTING_COUNT)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = existing_sessions
        mock_session.execute.return_value = mock_result

        # Call method
        await auth_service.create_session(user_id, "ip", "ua")
        
        # Logic: len(10) >= 5. Remove 10 - 5 + 1 = 6.
        assert mock_session.delete.call_count == 6
        deleted_args = [c[0][0] for c in mock_session.delete.call_args_list]
        expected_deleted = existing_sessions[:6]
        assert deleted_args == expected_deleted
