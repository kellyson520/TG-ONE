import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.lifecycle import LifecycleManager

@pytest.mark.asyncio
async def test_lifecycle_attributes():
    user_client = MagicMock()
    bot_client = MagicMock()
    
    # Reset singleton
    LifecycleManager._instance = None
    
    lifecycle = LifecycleManager(user_client, bot_client)
    
    assert hasattr(lifecycle, 'stop_event')
    assert isinstance(lifecycle.stop_event, asyncio.Event)
    assert hasattr(lifecycle, 'exit_code')
    assert lifecycle.exit_code == 0
    assert hasattr(lifecycle, 'shutdown')
    assert hasattr(lifecycle, 'stop')

@pytest.mark.asyncio
async def test_lifecycle_shutdown():
    user_client = MagicMock()
    bot_client = MagicMock()
    LifecycleManager._instance = None
    lifecycle = LifecycleManager(user_client, bot_client)
    
    lifecycle.shutdown(123)
    assert lifecycle.exit_code == 123
    assert lifecycle.stop_event.is_set()

@pytest.mark.asyncio
async def test_lifecycle_stop_sets_event():
    user_client = MagicMock()
    bot_client = MagicMock()
    LifecycleManager._instance = None
    lifecycle = LifecycleManager(user_client, bot_client)
    # Mock coordinator to avoid actual shutdown logic if needed, 
    # but based on code it just calls coordinator.shutdown
    lifecycle.coordinator = MagicMock()
    lifecycle.coordinator.shutdown = AsyncMock()
    lifecycle.coordinator.is_shutting_down.return_value = False

    await lifecycle.stop()
    assert lifecycle.stop_event.is_set()
