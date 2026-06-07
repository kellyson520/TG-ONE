import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import remote_config_sync_service as remote_module
from services.remote_config_sync_service import RemoteConfigSyncService


@pytest.mark.asyncio
async def test_reconnect_loop_retries_until_connect_sets_connected(tmp_path):
    service = RemoteConfigSyncService(config_dir=str(tmp_path))
    service.server_url = "wss://config.example"
    service.token = "token"
    service.reconnect_interval = 0.001
    attempts = 0

    async def fake_connect(server_url, token):
        nonlocal attempts
        attempts += 1
        assert server_url == service.server_url
        assert token == service.token
        if attempts == 2:
            service.is_connected = True

    service.connect = fake_connect

    await asyncio.wait_for(service._reconnect_loop(), timeout=0.2)

    assert attempts == 2


@pytest.mark.asyncio
async def test_reconnect_loop_timeout_is_observable(
    tmp_path,
    monkeypatch,
    caplog,
):
    service = RemoteConfigSyncService(config_dir=str(tmp_path))
    service.server_url = "wss://config.example"
    service.token = "token"
    service.reconnect_interval = 5.0
    attempts = 0

    async def fake_connect(server_url, token):
        nonlocal attempts
        attempts += 1
        assert server_url == service.server_url
        assert token == service.token

    async def fake_wait_for(awaitable, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        service._stop_event.set()
        raise asyncio.TimeoutError

    service.connect = fake_connect
    monkeypatch.setattr(
        "services.remote_config_sync_service.asyncio.wait_for",
        fake_wait_for,
    )
    caplog.set_level("DEBUG", logger="services.remote_config_sync_service")

    await service._reconnect_loop()

    assert attempts == 1
    assert "远程同步重连等待超时" in caplog.text


@pytest.mark.asyncio
async def test_connect_send_failure_closes_socket_before_reconnect(
    tmp_path,
    monkeypatch,
):
    service = RemoteConfigSyncService(config_dir=str(tmp_path))
    fake_ws = SimpleNamespace(
        send=AsyncMock(side_effect=RuntimeError("send failed")),
        close=AsyncMock(),
    )
    fake_websockets = SimpleNamespace(
        connect=AsyncMock(return_value=fake_ws),
    )
    monkeypatch.setattr(remote_module, "WEBSOCKETS_AVAILABLE", True)
    monkeypatch.setattr(remote_module, "websockets", fake_websockets)
    service._handle_messages = AsyncMock()
    service._start_reconnect = AsyncMock()

    await service.connect("wss://config.example", "token")

    assert service.is_connected is False
    fake_ws.close.assert_awaited_once()
    service._start_reconnect.assert_awaited_once()
