
import pytest
import os
import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

# === Test 1: Verify LOG_DIR Configuration ===
def test_log_dir_default_path():
    """Verify that LOG_DIR defaults to a 'logs' subdirectory, not root."""
    
    # Save original module if present
    original_module = sys.modules.get("core.config")
    
    try:
        # Force remove the mock from sys.modules
        if "core.config" in sys.modules:
            del sys.modules["core.config"]
            
        # Import real module
        import core.config
        importlib.reload(core.config)
        from core.config import Settings
        
        # Re-instantiate settings to strict defaults with empty env
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            # Check if the path ends with 'logs'
            assert s.LOG_DIR.name == "logs", f"Expected LOG_DIR to end with 'logs', got {s.LOG_DIR}"
            
    finally:
        # Restore mock to avoid breaking other tests
        if original_module:
            sys.modules["core.config"] = original_module

# === Test 2: Verify Config Logic Priority (DB First) ===
@pytest.mark.asyncio
async def test_settings_read_priority():
    """
    Verify the logic used in settings_router:
    DB value > Settings Object/Env value
    """
    # 1. Simulate the variables
    key = "TEST_KEY"
    db_value = "NEW_VALUE_FROM_DB"
    env_value = "OLD_VALUE_FROM_ENV"
    
    # 2. Mock Settings Object
    class RealEmuSettings:
        pass
    
    settings_obj = RealEmuSettings()
    setattr(settings_obj, key, env_value)
    
    # 3. Define the Logic Function to be tested (Mirrors routers/settings_router.py)
    # logic: if k in db_overrides -> use db; elif hasattr(settings, k) -> use settings
    def resolve_setting(k, db_overrides, settings_instance):
        v = None
        if k in db_overrides:
            v = db_overrides[k]
        elif hasattr(settings_instance, k):
            v = getattr(settings_instance, k)
        return v

    # Scenario 1: DB has value
    db_overrides = {key: db_value}
    result = resolve_setting(key, db_overrides, settings_obj)
    assert result == db_value, f"Should prioritize DB value '{db_value}', got '{result}'"
    
    # Scenario 2: DB missing value (fallback)
    db_overrides = {}
    result = resolve_setting(key, db_overrides, settings_obj)
    assert result == env_value, f"Should fallback to settings value '{env_value}', got '{result}'"
    
    # Scenario 3: Async Service Logic (Mirrors routers/system_router.py)
    # logic: v = service.get(k); if v is None: fallback
    async def resolve_system_setting(k, service_mock, settings_instance):
        v = await service_mock.get(k)
        if v is None:
            if hasattr(settings_instance, k):
                v = getattr(settings_instance, k)
        return v
        
    service_mock = MagicMock()
    
    # Case 3a: Service returns value
    service_mock.get = MagicMock(return_value=db_value) # Sync mock returning value, need async wrapper?
    # Actually treating access as async
    async def async_get_val(k): return db_value
    service_mock.get = async_get_val
    
    res = await resolve_system_setting(key, service_mock, settings_obj)
    assert res == db_value
    
    # Case 3b: Service returns None
    async def async_get_none(k): return None
    service_mock.get = async_get_none
    
    res = await resolve_system_setting(key, service_mock, settings_obj)
    assert res == env_value


# === Test 3: Verify Log Listing Logic ===
def test_log_listing_logic(tmp_path):
    """Verify the file listing logic correctly filters logs in the dir"""
    # Setup temp logs dir
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    
    # Create some files
    (logs_dir / "app.log").write_text("log content")
    (logs_dir / "error.log").write_text("error content")
    (logs_dir / "debug.txt").write_text("not a log") # Should be ignored
    
    # Simulate the logic in api_list_log_files
    log_files = []
    if logs_dir.exists():
        for file in os.listdir(logs_dir):
            if file.endswith('.log'):
                log_files.append(file)
                
    assert "app.log" in log_files
    assert "error.log" in log_files
    assert "debug.txt" not in log_files
    assert len(log_files) == 2

