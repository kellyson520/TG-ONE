import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from utils.network.bot_heartbeat import get_heartbeat, update_heartbeat, start_heartbeat, HEARTBEAT_KEY

class TestBotHeartbeat:
    @patch('utils.network.bot_heartbeat.get_persistent_cache')
    def test_get_heartbeat_empty(self, mock_get_cache):
        # Mock Cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get_cache.return_value = mock_cache
        
        hb = get_heartbeat()
        
        assert hb.get("age_seconds") is None
        assert hb.get("ts", 0) == 0

    @patch('utils.network.bot_heartbeat.get_persistent_cache')
    def test_get_heartbeat_valid(self, mock_get_cache):
        # Mock Cache
        mock_cache = MagicMock()
        now = time.time()
        # Ensure 'ts' is present and serialized correctly if using json.loads?
        # The code uses loads_json helper, we should assume it works or Mock it too?
        # Let's rely on loads_json from persistent_cache usually wrapping json.loads
        # But wait, utils.network.bot_heartbeat imports loads_json. 
        # So we should probably mocking loads_json or providing valid JSON string if loads_json calls json.loads
        
        import json
        payload = {"status": "ok", "ts": now - 10}
        mock_cache.get.return_value = json.dumps(payload)
        mock_get_cache.return_value = mock_cache
        
        with patch('utils.network.bot_heartbeat.loads_json', side_effect=json.loads):
            hb = get_heartbeat()
            assert hb["status"] == "ok"
            assert 9.9 < hb["age_seconds"] < 10.1

    @patch('utils.network.bot_heartbeat.get_persistent_cache')
    def test_update_heartbeat(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        
        update_heartbeat("running", details={"extra": 1})
        
        mock_cache.set.assert_called_once()
        args = mock_cache.set.call_args
        assert args[0][0] == HEARTBEAT_KEY
        # args[0][1] is json string, verify it
        import json
        data = json.loads(args[0][1])
        assert data["status"] == "running"
        assert data["extra"] == 1
        assert "ts" in data

    @pytest.mark.asyncio
    @patch('utils.network.bot_heartbeat.update_heartbeat')
    async def test_start_heartbeat_connected(self, mock_update, event_loop):
        mock_bot = MagicMock()
        mock_bot.is_connected = MagicMock(return_value=True) # Ensure it's treated as boolean or invoke-able?
        # The code uses: ok = bool(getattr(bot_client, "is_connected", False))
        # So it accesses property, not calls it.
        mock_bot.is_connected = True 
        mock_bot.get_me = AsyncMock(return_value={'id': 1})
        
        # We need to break the infinite loop.
        # One way is to raise CancelledError on sleep
        with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
             try:
                 await start_heartbeat(None, mock_bot)
             except asyncio.CancelledError:
                 pass
        
        # Should have called update_heartbeat at least once with "running"
        mock_update.assert_called()
        # Check calls
        calls = mock_update.call_args_list
        assert calls[0][0][0] == "running"

    @pytest.mark.asyncio
    @patch('utils.network.bot_heartbeat.update_heartbeat')
    async def test_start_heartbeat_disconnected(self, mock_update):
        mock_bot = MagicMock()
        mock_bot.is_connected = False
        
        with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
             try:
                 await start_heartbeat(None, mock_bot)
             except asyncio.CancelledError:
                 pass
        
        calls = mock_update.call_args_list
        assert calls[0][0][0] == "stopped"

    @pytest.mark.asyncio
    @patch('utils.network.bot_heartbeat.update_heartbeat')
    async def test_start_heartbeat_api_error(self, mock_update):
        mock_bot = MagicMock()
        mock_bot.is_connected = True
        mock_bot.get_me = AsyncMock(side_effect=Exception("API Fail"))
        
        with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
             try:
                 await start_heartbeat(None, mock_bot)
             except asyncio.CancelledError:
                 pass
        
        # Code says: except Exception: ok = True (assuming temp failure means still running but maybe lagging?)
        # See line 46-47: except Exception: ok = True
        calls = mock_update.call_args_list
        assert calls[0][0][0] == "running"
