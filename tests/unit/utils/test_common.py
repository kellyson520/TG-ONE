import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from core.helpers.common import (
    check_keywords,
    is_admin,
    get_user_id,
    get_admin_list
)
from services.rule.filter import RuleFilterService
from enums.enums import ForwardMode

# Mock keyword class
class MockKeyword:
    def __init__(self, keyword, is_regex=False, is_blacklist=False):
        self.keyword = keyword
        self.is_regex = is_regex
        self.is_blacklist = is_blacklist

# Mock rule class
class MockRule:
    def __init__(self, forward_mode, keywords, id=1, 
                 reverse_blacklist=False, reverse_whitelist=False,
                 is_filter_user_info=False):
        self.id = id
        self.forward_mode = forward_mode
        self.keywords = keywords
        self.enable_reverse_blacklist = reverse_blacklist
        self.enable_reverse_whitelist = reverse_whitelist
        self.is_filter_user_info = is_filter_user_info

@pytest.mark.asyncio
class TestCommonHelpers:
    
    # --- Keyword Checking Tests ---

    @patch('services.rule.filter.ACManager')
    async def test_check_keywords_fast_plain(self, mock_ac_manager):
        # Mock AC execution to fallback or behave predictably
        mock_ac = MagicMock()
        mock_ac.has_any_match.return_value = True
        mock_ac_manager.get_automaton.return_value = mock_ac
        
        # Test positive match via AC
        keywords = [MockKeyword("hello")]
        assert await RuleFilterService.check_keywords_fast(keywords, "hello there") is True

        # Test fallback manual check (simulate AC error or empty)
        mock_ac_manager.get_automaton.side_effect = Exception("AC Error")
        assert await RuleFilterService.check_keywords_fast(keywords, "hello there") is True  # Should fallback to loop
        assert await RuleFilterService.check_keywords_fast(keywords, "no match") is False

    async def test_check_keywords_fast_regex(self):
        keywords = [MockKeyword(r"\d{3}", is_regex=True)]
        assert await RuleFilterService.check_keywords_fast(keywords, "abc 123 def") is True
        assert await RuleFilterService.check_keywords_fast(keywords, "no numbers") is False

    @patch('services.rule.filter.ACManager')
    async def test_check_keywords_whitelist_mode(self, mock_ac_manager):
        mock_ac_manager.get_automaton.side_effect = Exception("Fallback")
        
        # Whitelist: Must match at least one whitelist keyword
        keywords = [MockKeyword("good", is_blacklist=False)]
        rule = MockRule(ForwardMode.WHITELIST, keywords)
        
        # Match
        assert await check_keywords(rule, "this is good") is True
        # No match
        assert await check_keywords(rule, "this is bad") is False

    @patch('services.rule.filter.ACManager')
    async def test_check_keywords_blacklist_mode(self, mock_ac_manager):
        mock_ac_manager.get_automaton.side_effect = Exception("Fallback")

        # Blacklist: Must NOT match any blacklist keyword
        keywords = [MockKeyword("bad", is_blacklist=True)]
        rule = MockRule(ForwardMode.BLACKLIST, keywords)
        
        # Match (should not forward)
        assert await check_keywords(rule, "this is bad") is False
        # No match (should forward)
        assert await check_keywords(rule, "this is good") is True

    @patch('services.rule.filter.ACManager')
    async def test_check_keywords_whitelist_reversed_blacklist(self, mock_ac_manager):
        mock_ac_manager.get_automaton.side_effect = Exception("Fallback")
        
        # Whitelist mode with reversed blacklist (blacklist becomes required whitelist 2)
        keywords = [
            MockKeyword("key1", is_blacklist=False),
            MockKeyword("key2", is_blacklist=True)
        ]
        # Enable reverse blacklist
        rule = MockRule(ForwardMode.WHITELIST, keywords, reverse_blacklist=True)
        
        # Match both key1 (whitelist) and key2 (reversed blacklist -> required)
        assert await check_keywords(rule, "key1 and key2") is True
        
        # Match only key1 (missing key2)
        assert await check_keywords(rule, "key1 only") is False

    @patch('services.rule.filter.ACManager')
    async def test_check_keywords_blacklist_reversed_whitelist(self, mock_ac_manager):
        mock_ac_manager.get_automaton.side_effect = Exception("Fallback")
        
        # Blacklist mode with reversed whitelist (whitelist becomes blocking blacklist 2)
        keywords = [
            MockKeyword("bad", is_blacklist=True),
            MockKeyword("good", is_blacklist=False)
        ]
        # Enable reverse whitelist
        rule = MockRule(ForwardMode.BLACKLIST, keywords, reverse_whitelist=True)
        
        # No bad words, no "good" (which is now bad) -> Forward
        assert await check_keywords(rule, "neutral text") is True
        
        # Contains "bad" -> Block
        assert await check_keywords(rule, "bad text") is False
        
        # Contains "good" (reversed to bad) -> Block
        assert await check_keywords(rule, "good text") is False

    # --- Admin Check Tests ---

    @patch('core.helpers.common.get_admin_list')
    async def test_is_admin_in_env_list(self, mock_get_admins):
        mock_get_admins.return_value = [12345]
        event = MagicMock()
        event.sender_id = 12345
        
        assert await is_admin(event) is True

    @patch('core.helpers.common.get_admin_list')
    @patch('core.container.container.db')
    async def test_is_admin_not_admin(self, mock_db, mock_get_admins):
        mock_get_admins.return_value = [12345]
        event = MagicMock()
        event.sender_id = 67890
        
        # Mock database session properly
        mock_session = AsyncMock()
        # Mock execute result -> scalar_one_or_none -> None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Context manager support
        mock_db.session.return_value.__aenter__.return_value = mock_session
        
        assert await is_admin(event) is False

    # --- Env Var Tests ---

    @patch('os.getenv')
    def test_get_admin_list_admins_set(self, mock_getenv):
        def side_effect(key, default=None):
            if key == "ADMINS": return "123, 456"
            return default
        mock_getenv.side_effect = side_effect
        
        admins = get_admin_list()
        assert admins == [123, 456]

    @patch('os.getenv')
    def test_get_admin_list_fallback_user_id(self, mock_getenv):
        def side_effect(key, default=None):
            if key == "ADMINS": return ""
            if key == "USER_ID": return "789"
            return default
        mock_getenv.side_effect = side_effect
        
        admins = get_admin_list()
        assert admins == [789]

    @patch('os.getenv')
    async def test_get_user_id(self, mock_getenv):
        mock_getenv.return_value = "999"
        assert await get_user_id() == 999
