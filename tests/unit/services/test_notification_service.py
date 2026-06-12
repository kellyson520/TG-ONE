import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.event_bus import EventBus
from services.notification_service import NotificationService


def _make_service(admin_ids=None):
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock()
    bus = EventBus()
    with patch("services.notification_service.settings") as mock_settings:
        mock_settings.ADMIN_IDS = admin_ids or []
        service = NotificationService(bot_client, bus)
    return service, bot_client, bus


class TestNotifyAdmins:
    @pytest.mark.asyncio
    async def test_sends_message_to_all_admins(self):
        service, bot_client, _ = _make_service([100, 200])
        await service.notify_admins("hello")

        assert bot_client.send_message.call_count == 2
        bot_client.send_message.assert_any_call(100, "\u2139\ufe0f **System Notification** [INFO]\n\nhello")
        bot_client.send_message.assert_any_call(200, "\u2139\ufe0f **System Notification** [INFO]\n\nhello")

    @pytest.mark.asyncio
    async def test_skips_when_no_admins(self):
        service, bot_client, _ = _make_service([])
        await service.notify_admins("hello")

        bot_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_level_icon(self):
        service, bot_client, _ = _make_service([1])
        await service.notify_admins("boom", level="ERROR")

        msg = bot_client.send_message.call_args[0][1]
        assert msg.startswith("\U0001f6a8")
        assert "[ERROR]" in msg

    @pytest.mark.asyncio
    async def test_warning_level_icon(self):
        service, bot_client, _ = _make_service([1])
        await service.notify_admins("warn", level="WARNING")

        msg = bot_client.send_message.call_args[0][1]
        assert msg.startswith("\u26a0\ufe0f")

    @pytest.mark.asyncio
    async def test_success_level_icon(self):
        service, bot_client, _ = _make_service([1])
        await service.notify_admins("ok", level="SUCCESS")

        msg = bot_client.send_message.call_args[0][1]
        assert msg.startswith("\u2705")


class TestSendSafe:
    @pytest.mark.asyncio
    async def test_logs_warning_on_send_failure(self):
        service, bot_client, _ = _make_service([1])
        bot_client.send_message.side_effect = RuntimeError("network down")

        with patch("services.notification_service.logger") as mock_logger:
            await service._send_safe(1, "msg")

        mock_logger.warning.assert_called_once()
        assert "Failed to send notification" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_does_not_raise_on_send_failure(self):
        service, bot_client, _ = _make_service([1])
        bot_client.send_message.side_effect = RuntimeError("boom")

        await service._send_safe(1, "msg")


class TestAdminIdLoading:
    def test_parses_valid_ids(self):
        service, _, _ = _make_service([10, 20, 30])
        assert service.admin_ids == [10, 20, 30]

    def test_skips_invalid_ids(self):
        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [123, "not_a_number", 456]
            bus = EventBus()
            bot_client = MagicMock()
            with patch("services.notification_service.logger") as mock_logger:
                service = NotificationService(bot_client, bus)

        assert service.admin_ids == [123, 456]
        mock_logger.warning.assert_called()


class TestEventSubscriptions:
    @pytest.mark.asyncio
    async def test_on_system_error_sends_formatted_message(self):
        service, bot_client, bus = _make_service([99])

        await bus.publish("ERROR_SYSTEM", {"module": "test_mod", "error": "bad stuff"}, wait=True)

        await asyncio.sleep(0.05)
        msg = bot_client.send_message.call_args[0][1]
        assert "test_mod" in msg
        assert "bad stuff" in msg
        assert "[ERROR]" in msg

    @pytest.mark.asyncio
    async def test_on_system_alert_sends_warning(self):
        service, bot_client, bus = _make_service([99])

        await bus.publish("SYSTEM_ALERT", {"message": "disk full"}, wait=True)

        await asyncio.sleep(0.05)
        msg = bot_client.send_message.call_args[0][1]
        assert "disk full" in msg
        assert "[WARNING]" in msg

    @pytest.mark.asyncio
    async def test_on_security_alert_critical_only(self):
        service, bot_client, bus = _make_service([99])

        await bus.publish(
            "AUTH_LOGIN_FAILED",
            {"severity": "critical", "message": "brute force", "ip": "1.2.3.4"},
            wait=True,
        )

        await asyncio.sleep(0.05)
        msg = bot_client.send_message.call_args[0][1]
        assert "brute force" in msg
        assert "1.2.3.4" in msg

    @pytest.mark.asyncio
    async def test_on_security_alert_ignores_non_critical(self):
        service, bot_client, bus = _make_service([99])

        await bus.publish(
            "AUTH_LOGIN_FAILED",
            {"severity": "info", "message": "single fail"},
            wait=True,
        )

        await asyncio.sleep(0.05)
        bot_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_system_alert_defaults_message(self):
        service, bot_client, bus = _make_service([99])

        await bus.publish("SYSTEM_ALERT", {}, wait=True)

        await asyncio.sleep(0.05)
        msg = bot_client.send_message.call_args[0][1]
        assert "System Alert" in msg


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_all_admins_receive_concurrent_sends(self):
        admins = list(range(1, 51))
        service, bot_client, _ = _make_service(admins)

        await service.notify_admins("bulk")

        assert bot_client.send_message.call_count == 50

    @pytest.mark.asyncio
    async def test_send_failure_does_not_block_others(self):
        service, bot_client, _ = _make_service([1, 2, 3])
        call_order = []

        async def send_side_effect(uid, msg):
            call_order.append(uid)
            if uid == 2:
                raise RuntimeError("fail")
        bot_client.send_message.side_effect = send_side_effect

        await service.notify_admins("msg")

        assert set(call_order) == {1, 2, 3}


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_send_safe_returns_none_on_success(self):
        service, _, _ = _make_service([1])
        result = await service._send_safe(1, "msg")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_rapid_errors_dont_crash(self):
        service, bot_client, _ = _make_service([1])
        bot_client.send_message.side_effect = RuntimeError("down")

        for _ in range(100):
            await service._send_safe(1, "msg")

    @pytest.mark.asyncio
    async def test_system_error_with_missing_fields(self):
        service, bot_client, bus = _make_service([99])

        await bus.publish("ERROR_SYSTEM", {}, wait=True)

        await asyncio.sleep(0.05)
        msg = bot_client.send_message.call_args[0][1]
        assert "Unknown" in msg
