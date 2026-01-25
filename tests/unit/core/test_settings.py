"""
Unit tests for application settings.
Tests Pydantic validation and default values.
"""
import pytest
from core.config import Settings
from pathlib import Path
import os

class TestSettingsLogic:
    def test_debug(self):
        print(f"DEBUG: Settings class type: {type(Settings)}")
        print(f"DEBUG: Settings class: {Settings}")
        s = Settings()
        print(f"DEBUG: Instance type: {type(s)}")
        print(f"DEBUG: Instance: {s}")
    
    def test_default_paths(self):
        """Test that default paths are correctly calculated relative to project root."""
        # We can't easily mock __file__ inside config.py for settings instantiation,
        # but we can verify consistency of an instance.
        s = Settings()
        assert s.BASE_DIR.name == "TG ONE"
        assert s.DOWNLOAD_DIR == s.BASE_DIR / "downloads"
        assert s.SESSION_DIR == s.BASE_DIR / "sessions"

    def test_parse_list_fields_comma(self):
        """Test validation of comma-separated string to list."""
        # We manually trigger validation or create instance with env mock
        # But easier to just test the class method directly if possible
        raw = "03:30, 15:00"
        result = Settings.parse_list_fields(raw)
        assert result == ["03:30", "15:00"]

    def test_parse_list_fields_json(self):
        """Test validation of JSON string to list."""
        raw = '["01:00", "02:00"]'
        result = Settings.parse_list_fields(raw)
        assert result == ["01:00", "02:00"]

    def test_parse_list_fields_already_list(self):
        """Test that it doesn't break if already a list."""
        raw = ["a", "b"]
        result = Settings.parse_list_fields(raw)
        assert result == ["a", "b"]

    def test_env_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("APP_ENV", "testing")
        monkeypatch.setenv("WEB_PORT", "9999")
        
        # Instantiate fresh settings (ignoring global lru_cache for this test)
        s = Settings(_env_file=None) # No env file to ensure monkeypatch is used
        assert s.APP_ENV == "testing"
        assert s.WEB_PORT == 9999
