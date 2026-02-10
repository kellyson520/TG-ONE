
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.dedup.engine import SmartDeduplicator

@pytest.fixture
def dedup():
    dedup = SmartDeduplicator()
    
    # Mock repositories (AsyncMock for async methods)
    dedup._repo = MagicMock()
    dedup._repo.exists_media_signature = AsyncMock(return_value=False)
    dedup._repo.check_content_hash_duplicate = AsyncMock(return_value=(False, ""))
    dedup._repo.load_config = AsyncMock(return_value={})
    dedup._repo.save_config = AsyncMock()
    
    dedup._pcache_repo = MagicMock()
    dedup._pcache_repo.get = AsyncMock(return_value=None)
    dedup._pcache_repo.set = AsyncMock()
    
    # Disable components
    dedup.bloom_filter = None 
    dedup.hll = None
    
    return dedup

@pytest.mark.asyncio
async def test_lazy_config_loading(dedup):
    """Test that config is loaded on first check_duplicate call"""
    msg = MagicMock()
    chat_id = 12345
    
    # Disable strategies to isolate config loading logic
    dedup.strategies = []
    
    # Setup mock config return
    mock_config = {"enable_dedup": False, "threshold": 0.99}
    dedup._repo.load_config.return_value = mock_config
    
    assert dedup._config_loaded is False
    assert dedup.config.enable_dedup is True # Default
    
    # First call triggers load
    with patch("services.dedup.tools.generate_signature", return_value="sig:1"):
        with patch("services.dedup.tools.generate_content_hash", return_value="hash:1"):
            await dedup.check_duplicate(msg, chat_id)
        
    assert dedup._config_loaded is True
    dedup._repo.load_config.assert_called_once()
    
    # Verify config updated
    assert dedup.config.enable_dedup is False
    
    # Second call should NOT trigger load
    with patch("services.dedup.tools.generate_signature", return_value="sig:1"):
        with patch("services.dedup.tools.generate_content_hash", return_value="hash:1"):
            await dedup.check_duplicate(msg, chat_id)
        
    dedup._repo.load_config.assert_called_once() # Count remains 1

@pytest.mark.asyncio
async def test_update_config_persistence(dedup):
    """Test that updating config persists it to repo"""
    new_config = {"enable_dedup": False, "time_window_hours": 48}
    
    await dedup.update_config(new_config)
    
    # Verify local update
    assert dedup.config.enable_dedup is False
    assert dedup.config.time_window_hours == 48
    
    # Verify persistence call
    dedup._repo.save_config.assert_called_once()
    saved_arg = dedup._repo.save_config.call_args[0][0]
    
    # Check that saved arg contains all config fields (asdict was used)
    assert saved_arg['enable_dedup'] is False
    assert saved_arg['time_window_hours'] == 48
    assert 'max_text_cache_size' in saved_arg

@pytest.mark.asyncio
async def test_build_config_cloning(dedup):
    """Test that _build_config correctly clones global config"""
    # Set global config
    dedup.config.enable_dedup = False
    dedup.config.time_window_hours = 100
    
    # Override via rule_config
    rule_config = {"enable_dedup": True}
    
    final_config = dedup._build_config(rule_config, skip_media_sig=True, readonly=True)
    
    # verified overrides
    assert final_config.enable_dedup is True
    assert final_config.skip_media_sig is True
    assert final_config.readonly is True
    
    # verified inheritance from global
    assert final_config.time_window_hours == 100
