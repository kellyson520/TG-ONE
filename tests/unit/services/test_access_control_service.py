import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.access_control_service import AccessControlService
from models.models import AccessControlList

@pytest.fixture
def ac_service():
    return AccessControlService()

@pytest.mark.asyncio
async def test_check_ip_access_default_allow(ac_service):
    """If no rules exist, default to allow."""
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        # Mock result for both select statements
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        allowed = await ac_service.check_ip_access("1.2.3.4")
        assert allowed is True

@pytest.mark.asyncio
async def test_check_ip_access_blocked(ac_service):
    """If IP is in blacklist, deny."""
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_rule = MagicMock(spec=AccessControlList)
        mock_rule.type = "BLOCK"
        mock_rule.ip_address = "1.2.3.4"
        
        mock_result.scalars.return_value.all.return_value = [mock_rule]
        mock_session.execute.return_value = mock_result
        
        allowed = await ac_service.check_ip_access("1.2.3.4")
        assert allowed is False

@pytest.mark.asyncio
async def test_check_ip_access_not_in_whitelist(ac_service):
    """If a whitelist exists and IP is not in it, deny."""
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        # Mock result for the select statement that returns rules
        mock_result = MagicMock()
        mock_allow_rule = MagicMock(spec=AccessControlList)
        mock_allow_rule.type = "ALLOW"
        mock_allow_rule.ip_address = "1.1.1.1"  # Different IP than tested
        
        mock_result.scalars.return_value.all.return_value = [mock_allow_rule]
        mock_session.execute.return_value = mock_result
        
        allowed = await ac_service.check_ip_access("1.2.3.4")
        assert allowed is False

@pytest.mark.asyncio
async def test_add_rule_new(ac_service):
    """Test adding a new rule."""
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        # IP doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        rule = await ac_service.add_rule("8.8.8.8", "ALLOW", "Google DNS")
        
        assert rule.ip_address == "8.8.8.8"
        assert rule.type == "ALLOW"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_delete_rule_success(ac_service):
    """Test deleting an existing rule."""
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        mock_rule = MagicMock(spec=AccessControlList)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rule
        mock_session.execute.return_value = mock_result
        
        success = await ac_service.delete_rule("192.168.1.1")
        
        assert success is True
        mock_session.delete.assert_called_once_with(mock_rule)
        mock_session.commit.assert_called_once()
