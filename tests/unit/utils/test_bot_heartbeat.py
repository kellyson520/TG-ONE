import asyncio
import importlib
import json
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.modules.pop("services.network.bot_heartbeat", None)
bot_heartbeat = importlib.import_module("services.network.bot_heartbeat")
get_heartbeat = bot_heartbeat.get_heartbeat
update_heartbeat = bot_heartbeat.update_heartbeat
start_heartbeat = bot_heartbeat.start_heartbeat
HEARTBEAT_KEY = bot_heartbeat.HEARTBEAT_KEY


class TestBotHeartbeat:
    @patch("services.network.bot_heartbeat.get_persistent_cache")
    def test_get_heartbeat_empty(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get_cache.return_value = mock_cache

        hb = get_heartbeat()

        assert hb.get("age_seconds") is None
        assert hb.get("ts", 0) == 0

    @patch("services.network.bot_heartbeat.get_persistent_cache")
    def test_get_heartbeat_valid(self, mock_get_cache):
        mock_cache = MagicMock()
        now = time.time()
        payload = {"status": "ok", "ts": now - 10}
        mock_cache.get.return_value = json.dumps(payload)
        mock_get_cache.return_value = mock_cache

        with patch(
            "services.network.bot_heartbeat.loads_json",
            side_effect=json.loads,
        ):
            hb = get_heartbeat()
            assert hb["status"] == "ok"
            assert 9.9 < hb["age_seconds"] < 10.1

    @patch("services.network.bot_heartbeat.get_persistent_cache")
    def test_update_heartbeat(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        update_heartbeat("running", details={"extra": 1})

        mock_cache.set.assert_called_once()
        args = mock_cache.set.call_args
        assert args[0][0] == HEARTBEAT_KEY
        data = json.loads(args[0][1])
        assert data["status"] == "running"
        assert data["extra"] == 1
        assert "ts" in data

    @pytest.mark.asyncio
    @patch("services.network.bot_heartbeat.update_heartbeat")
    async def test_start_heartbeat_connected(self, mock_update, event_loop):
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.get_me = AsyncMock(return_value={"id": 1})

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            await start_heartbeat(None, mock_bot)

        calls = mock_update.call_args_list
        assert calls[0][0][0] == "running"

    @pytest.mark.asyncio
    @patch("services.network.bot_heartbeat.update_heartbeat")
    async def test_start_heartbeat_disconnected(self, mock_update):
        mock_bot = MagicMock()
        mock_bot.is_connected = False

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            await start_heartbeat(None, mock_bot)

        calls = mock_update.call_args_list
        assert calls[0][0][0] == "stopped"

    @pytest.mark.asyncio
    @patch("services.network.bot_heartbeat.update_heartbeat")
    async def test_start_heartbeat_api_error(self, mock_update):
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.get_me = AsyncMock(side_effect=Exception("API Fail"))

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            await start_heartbeat(None, mock_bot)

        calls = mock_update.call_args_list
        assert calls[0][0][0] == "running"

    @pytest.mark.asyncio
    @patch("services.network.bot_heartbeat.update_heartbeat")
    async def test_start_heartbeat_callable_is_connected_false(
        self,
        mock_update,
    ):
        mock_bot = MagicMock()
        mock_bot.is_connected = MagicMock(return_value=False)
        mock_bot.get_me = AsyncMock()

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            await start_heartbeat(None, mock_bot)

        calls = mock_update.call_args_list
        assert calls[0][0][0] == "stopped"
        mock_bot.get_me.assert_not_awaited()
