from contextlib import asynccontextmanager
import logging
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock
from services.access_control_service import AccessControlService
from models.models import AccessControlList

@pytest.fixture
def ac_service():
    return AccessControlService()


def _session_with_result(result):
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


def _patch_get_session(monkeypatch, session):
    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield session

    monkeypatch.setattr(
        "services.access_control_service.container.db.get_session",
        fake_get_session,
    )

@pytest.mark.asyncio
async def test_check_ip_access_default_allow(ac_service, monkeypatch):
    """If no rules exist, default to allow."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = _session_with_result(mock_result)
    _patch_get_session(monkeypatch, mock_session)

    allowed = await ac_service.check_ip_access("1.2.3.4")
    assert allowed is True

@pytest.mark.asyncio
async def test_check_ip_access_blocked(ac_service, monkeypatch):
    """If IP is in blacklist, deny."""
    mock_result = MagicMock()
    mock_rule = MagicMock(spec=AccessControlList)
    mock_rule.type = "BLOCK"
    mock_rule.ip_address = "1.2.3.4"
    mock_result.scalars.return_value.all.return_value = [mock_rule]
    mock_session = _session_with_result(mock_result)
    _patch_get_session(monkeypatch, mock_session)

    allowed = await ac_service.check_ip_access("1.2.3.4")
    assert allowed is False

@pytest.mark.asyncio
async def test_check_ip_access_not_in_whitelist(ac_service, monkeypatch):
    """If a whitelist exists and IP is not in it, deny."""
    mock_result = MagicMock()
    mock_allow_rule = MagicMock(spec=AccessControlList)
    mock_allow_rule.type = "ALLOW"
    mock_allow_rule.ip_address = "1.1.1.1"  # Different IP than tested
    mock_result.scalars.return_value.all.return_value = [mock_allow_rule]
    mock_session = _session_with_result(mock_result)
    _patch_get_session(monkeypatch, mock_session)

    allowed = await ac_service.check_ip_access("1.2.3.4")
    assert allowed is False

@pytest.mark.asyncio
async def test_check_ip_access_logs_invalid_block_rule_and_continues(
    ac_service,
    caplog,
):
    """Invalid block rules are observable and do not stop later rule checks."""
    ac_service._get_rules = AsyncMock(
        return_value=[
            SimpleNamespace(type="BLOCK", ip_address="bad-cidr/24"),
            SimpleNamespace(type="BLOCK", ip_address="1.2.3.4"),
        ]
    )
    caplog.set_level(logging.DEBUG, logger="services.access_control_service")

    allowed = await ac_service.check_ip_access("1.2.3.4")

    assert allowed is False
    assert "AccessControlService skipped invalid block rule" in caplog.text
    assert "bad-cidr/24" in caplog.text
    assert "client_ip=1.2.3.4" in caplog.text

@pytest.mark.asyncio
async def test_check_ip_access_logs_invalid_allow_rule_and_continues(
    ac_service,
    caplog,
):
    """Invalid allow rules are observable and do not block valid allow rules."""
    ac_service._get_rules = AsyncMock(
        return_value=[
            SimpleNamespace(type="ALLOW", ip_address="bad-cidr/24"),
            SimpleNamespace(type="ALLOW", ip_address="1.2.3.0/24"),
        ]
    )
    caplog.set_level(logging.DEBUG, logger="services.access_control_service")

    allowed = await ac_service.check_ip_access("1.2.3.4")

    assert allowed is True
    assert "AccessControlService skipped invalid allow rule" in caplog.text
    assert "bad-cidr/24" in caplog.text
    assert "client_ip=1.2.3.4" in caplog.text

@pytest.mark.asyncio
async def test_add_rule_new(ac_service, monkeypatch):
    """Test adding a new rule."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = _session_with_result(mock_result)
    _patch_get_session(monkeypatch, mock_session)

    rule = await ac_service.add_rule("8.8.8.8", "ALLOW", "Google DNS")

    assert rule.ip_address == "8.8.8.8"
    assert rule.type == "ALLOW"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_delete_rule_success(ac_service, monkeypatch):
    """Test deleting an existing rule."""
    mock_rule = MagicMock(spec=AccessControlList)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_rule
    mock_session = _session_with_result(mock_result)
    _patch_get_session(monkeypatch, mock_session)

    success = await ac_service.delete_rule("192.168.1.1")

    assert success is True
    mock_session.delete.assert_awaited_once_with(mock_rule)
    mock_session.commit.assert_awaited_once()
