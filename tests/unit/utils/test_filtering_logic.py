"""
Unit tests for filtering logic in common helpers.
Tests keyword matching and forward mode logic.
"""
import pytest
from unittest.mock import MagicMock
from core.helpers.common import check_keyword_match, process_whitelist_mode, process_blacklist_mode

class TestFilteringLogic:
    
    @pytest.mark.asyncio
    async def test_check_keyword_match_simple(self):
        """Test simple substring matching."""
        keyword = MagicMock()
        keyword.keyword = "test"
        keyword.is_regex = False
        
        assert await check_keyword_match(keyword, "this is a test message") is True
        assert await check_keyword_match(keyword, "THIS IS A TEST") is True # Case insensitive
        assert await check_keyword_match(keyword, "no match here") is False

    @pytest.mark.asyncio
    async def test_check_keyword_match_regex(self):
        """Test regex matching."""
        keyword = MagicMock()
        keyword.keyword = r"^start.*end$"
        keyword.is_regex = True
        
        assert await check_keyword_match(keyword, "start of text end") is True
        assert await check_keyword_match(keyword, "start middle") is False
        
        # Invalid regex handling
        keyword.keyword = "["
        assert await check_keyword_match(keyword, "something") is False

    @pytest.mark.asyncio
    async def test_process_whitelist_mode(self):
        """Test WHITELIST mode logic."""
        rule = MagicMock()
        kw1 = MagicMock(keyword="apple", is_blacklist=False, is_regex=False)
        kw2 = MagicMock(keyword="banana", is_blacklist=False, is_regex=False)
        rule.keywords = [kw1, kw2]
        
        # Match one
        assert await process_whitelist_mode(rule, "i like apple", reverse_blacklist=False) is True
        # No match
        assert await process_whitelist_mode(rule, "i like cherry", reverse_blacklist=False) is False

    @pytest.mark.asyncio
    async def test_process_blacklist_mode(self):
        """Test BLACKLIST mode logic."""
        rule = MagicMock()
        kw1 = MagicMock(keyword="spam", is_blacklist=True, is_regex=False)
        rule.keywords = [kw1]
        
        # Match blacklist -> False
        assert await process_blacklist_mode(rule, "this is spam", reverse_whitelist=False) is False
        # No match -> True
        assert await process_blacklist_mode(rule, "good message", reverse_whitelist=False) is True

    @pytest.mark.asyncio
    async def test_whitelist_with_reverse_blacklist(self):
        """Test WHITELIST mode with reverse_blacklist enabled (second whitelist)."""
        rule = MagicMock()
        kw_white = MagicMock(keyword="apple", is_blacklist=False, is_regex=False)
        kw_black = MagicMock(keyword="fresh", is_blacklist=True, is_regex=False)
        rule.keywords = [kw_white, kw_black]
        
        # Must match both: "apple" AND "fresh" (because black is reversed)
        assert await process_whitelist_mode(rule, "fresh apple", reverse_blacklist=True) is True
        assert await process_whitelist_mode(rule, "rotten apple", reverse_blacklist=True) is False
        assert await process_whitelist_mode(rule, "fresh orange", reverse_blacklist=True) is False
