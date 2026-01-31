from hypothesis import given, strategies as st
from core.helpers.id_utils import normalize_chat_id, build_candidate_telegram_ids
from typing import Union
import pytest

@given(st.one_of(st.integers(), st.text()))
def test_normalize_chat_id_fuzz(chat_id):
    # Should not crash
    result = normalize_chat_id(chat_id)
    assert isinstance(result, str)

@given(st.one_of(st.integers(), st.text()))
def test_build_candidate_telegram_ids_fuzz(raw_id):
    # Should not crash
    result = build_candidate_telegram_ids(raw_id)
    assert isinstance(result, set)
    for vid in result:
        assert isinstance(vid, str)

if __name__ == "__main__":
    pass
