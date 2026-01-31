import pytest
import asyncio
from unittest.mock import MagicMock, patch
from core.helpers.sleep_manager import SleepManager

class TestSleepManager:
    
    @pytest.mark.asyncio
    async def test_sleep_wake_cycle(self):
        manager = SleepManager()
        manager.SLEEP_TIMEOUT = 0.1  # Fast timeout
        
        sleep_cb = MagicMock()
        wake_cb = MagicMock()
        
        manager.register_on_sleep(sleep_cb)
        manager.register_on_wake(wake_cb)
        
        # Start activity
        manager.record_activity()
        assert not manager.is_sleeping
        
        # Manually trigger check logic (since we can't easily wait for loop in unit test without blocking)
        # We simulate the passage of time
        await asyncio.sleep(0.2)
        
        # Trigger the internal check logic manually
        # Note: In real usage, start_monitor runs a loop. Here we test the logic directly.
        if not manager.is_sleeping:
             # Logic from _resource_monitor_loop but we access private methods for testing or replicate logic?
             # _go_to_sleep is async.
             # We can't access `manager._last_activity` easily if private, but we can verify public behavior?
             # Actually attributes are `_last_activity`.
             
             # Let's inspect internal state briefly for the test
             import time
             if time.time() - manager._last_activity > manager.SLEEP_TIMEOUT:
                 await manager._go_to_sleep()
                 
        assert manager.is_sleeping
        sleep_cb.assert_called_once()
        
        # Now Wake Up
        manager.record_activity()
        assert not manager.is_sleeping
        wake_cb.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_already_sleeping(self):
        manager = SleepManager()
        manager._is_sleeping = True
        
        sleep_cb = MagicMock()
        manager.register_on_sleep(sleep_cb)
        
        await manager._go_to_sleep()
        sleep_cb.assert_not_called()
        
