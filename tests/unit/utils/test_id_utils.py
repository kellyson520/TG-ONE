"""
Unit tests for ID utilities.
Tests normalization and candidate generation logic for Telegram IDs.
"""
import pytest
from utils.helpers.id_utils import normalize_chat_id, build_candidate_telegram_ids

class TestIdUtils:
    
    @pytest.mark.parametrize("input_id, expected", [
        (-1001234567890, "1234567890"),
        ("-1001234567890", "1234567890"),
        (-1234567890, "1234567890"),
        ("-1234567890", "1234567890"),
        (1234567890, "1234567890"),
        ("1234567890", "1234567890"),
        (0, "0"),
        ("non_numeric", "non_numeric"),
    ])
    def test_normalize_chat_id(self, input_id, expected):
        """Test normalization of various Chat ID formats."""
        assert normalize_chat_id(input_id) == expected

    def test_build_candidate_ids_supergroup(self):
        """Test candidate generation for -100 style IDs."""
        raw_id = -1001234567890
        candidates = build_candidate_telegram_ids(raw_id)
        
        # Should contain:
        # 1. Original string: "-1001234567890"
        # 2. Normalized: "1234567890"
        # 3. Numeric string: "-1001234567890"
        # 4. Absolute numeric string: "1001234567890"
        # 5. Prefixed formats: "-1001001234567890", "-1001234567890"
        
        assert "-1001234567890" in candidates
        assert "1234567890" in candidates
        assert "1001234567890" in candidates
        assert "-1234567890" in candidates
        assert "1234567890" in candidates

    def test_build_candidate_ids_simple_group(self):
        """Test candidate generation for simple negative IDs."""
        raw_id = -12345
        candidates = build_candidate_telegram_ids(raw_id)
        
        assert "-12345" in candidates
        assert "12345" in candidates
        assert "-10012345" in candidates

    def test_build_candidate_ids_positive_user(self):
        """Test candidate generation for positive user IDs."""
        raw_id = 98765
        candidates = build_candidate_telegram_ids(raw_id)
        
        assert "98765" in candidates
        assert "-98765" in candidates
        assert "-10098765" in candidates

    def test_build_candidate_ids_strings(self):
        """Test candidate generation for string inputs."""
        assert "my_username" in build_candidate_telegram_ids("my_username")
        assert "123" in build_candidate_telegram_ids("123")
