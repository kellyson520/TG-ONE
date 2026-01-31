from hypothesis import given, strategies as st
from services.rule.filter import RuleFilterService
from core.algorithms.ac_automaton import ACAutomaton
from dataclasses import dataclass
from typing import Optional
import pytest

@dataclass
class KeywordDTO:
    keyword: str
    is_blacklist: bool = False
    is_regex: bool = False

@given(st.text())
def test_ac_automaton_fuzz(text):
    ac = ACAutomaton()
    # Adding a simple keyword to test building and searching
    ac.add_keyword("test")
    ac.build()
    # Should not crash
    ac.search(text)
    ac.has_any_match(text)

@given(
    st.lists(st.builds(KeywordDTO, keyword=st.text(min_size=1, max_size=50), is_regex=st.booleans())),
    st.text(),
    st.integers(min_value=1, max_value=1000)
)
@pytest.mark.asyncio
async def test_check_keywords_fast_fuzz(keywords, message_text, rule_id):
    # Should not crash
    # Note: Regex patterns might be invalid, but check_keywords_fast handles that with try-except
    await RuleFilterService.check_keywords_fast(keywords, message_text, rule_id)

if __name__ == "__main__":
    import asyncio
    # For local manual testing if needed
    pass
