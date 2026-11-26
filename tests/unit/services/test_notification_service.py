"""Tests for services/notification_service.py"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestNotificationService:
    """Test NotificationService"""

    def _make_service(self, admin_ids=None):
        """Helper to create NotificationService with mocked dependencies"""
        with patch("services.notification_service.settings") as mock_settings, \
             patch("services.notification_service.EventBus") as mock_bus_cls, \
             patch("services.notification_service.TelegramClient"):
            mock_settings.ADMIN_IDS = admin_ids or []
            mock_bus = MagicMock()
            mock_bus_cls.return_value = mock_bus
            mock_client = AsyncMock()

            from services.notification_service import NotificationService
            svc = NotificationService(bot_client=mock_client, event_bus=mock_bus)
            return svc, mock_client, mock_bus

    def test_init_loads_admin_ids(self):
        svc, _, _ = self._make_service(admin_ids=["123", "456"])
        assert svc.admin_ids == [123, 456]

    def test_init_skips_invalid_admin_ids(self):
        svc, _, _ = self._make_service(admin_ids=["123", "bad", "789"])
        assert svc.admin_ids == [123, 789]

    def test_init_empty_admin_ids(self):
        svc, _, _ = self._make_service(admin_ids=[])
        assert svc.admin_ids == []

    def test_init_subscribes_events(self):
        _, _, mock_bus = self._make_service()
        assert mock_bus.subscribe.call_count == 3
        events_subscribed = [call.args[0] for call in mock_bus.subscribe.call_args_list]
        assert "ERROR_SYSTEM" in events_subscribed
        assert "SYSTEM_ALERT" in events_subscribed
        assert "AUTH_LOGIN_FAILED" in events_subscribed

    @pytest.mark.asyncio
    async def test_notify_admins_sends_to_all(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1", "2", "3"])
        await svc.notify_admins("test message")
        assert mock_client.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_notify_admins_no_admins(self):
        svc, mock_client, _ = self._make_service(admin_ids=[])
        await svc.notify_admins("test message")
        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_admins_formats_error_level(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc.notify_admins("oops", level="ERROR")
        msg = mock_client.send_message.call_args[0][1]
        assert "🚨" in msg
        assert "ERROR" in msg

    @pytest.mark.asyncio
    async def test_notify_admins_formats_warning_level(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc.notify_admins("careful", level="WARNING")
        msg = mock_client.send_message.call_args[0][1]
        assert "⚠️" in msg

    @pytest.mark.asyncio
    async def test_notify_admins_formats_success_level(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc.notify_admins("yay", level="SUCCESS")
        msg = mock_client.send_message.call_args[0][1]
        assert "✅" in msg

    @pytest.mark.asyncio
    async def test_send_safe_handles_exception(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        mock_client.send_message.side_effect = Exception("network error")
        # Should not raise
        await svc._send_safe(1, "test")

    @pytest.mark.asyncio
    async def test_on_system_error(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc._on_system_error({"module": "test_mod", "error": "boom"})
        msg = mock_client.send_message.call_args[0][1]
        assert "test_mod" in msg
        assert "boom" in msg
        assert "🚨" in msg

    @pytest.mark.asyncio
    async def test_on_system_alert(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc._on_system_alert({"message": "disk full"})
        msg = mock_client.send_message.call_args[0][1]
        assert "disk full" in msg

    @pytest.mark.asyncio
    async def test_on_security_alert_critical(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc._on_security_alert({"severity": "critical", "message": "brute force", "ip": "1.2.3.4"})
        msg = mock_client.send_message.call_args[0][1]
        assert "brute force" in msg
        assert "1.2.3.4" in msg

    @pytest.mark.asyncio
    async def test_on_security_alert_non_critical_ignored(self):
        svc, mock_client, _ = self._make_service(admin_ids=["1"])
        await svc._on_security_alert({"severity": "low", "message": "minor"})
        mock_client.send_message.assert_not_called()
