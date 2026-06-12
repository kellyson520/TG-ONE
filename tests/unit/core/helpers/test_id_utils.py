import pytest
from core.helpers.id_utils import normalize_chat_id, build_candidate_telegram_ids


class TestNormalizeChatId:
    def test_super_group_format(self):
        assert normalize_chat_id(-1002815974674) == '2815974674'

    def test_negative_number(self):
        assert normalize_chat_id(-2815974674) == '2815974674'

    def test_positive_number(self):
        assert normalize_chat_id(2815974674) == '2815974674'

    def test_string_input(self):
        assert normalize_chat_id('-1002815974674') == '2815974674'

    def test_zero(self):
        assert normalize_chat_id(0) == '0'

    def test_non_numeric_string(self):
        result = normalize_chat_id('abc')
        assert result == 'abc'

    def test_small_negative(self):
        assert normalize_chat_id(-123) == '123'


class TestBuildCandidateIds:
    def test_super_group_has_candidates(self):
        cands = build_candidate_telegram_ids(-1002815974674)
        assert '2815974674' in cands

    def test_positive_id_has_variants(self):
        cands = build_candidate_telegram_ids(12345)
        assert '12345' in cands
        assert '-12345' in cands
        assert '-10012345' in cands

    def test_string_input(self):
        cands = build_candidate_telegram_ids('999')
        assert '999' in cands

    def test_non_numeric(self):
        cands = build_candidate_telegram_ids('mygroup')
        assert 'mygroup' in cands
        assert len(cands) >= 1

    def test_returns_set(self):
        cands = build_candidate_telegram_ids(42)
        assert isinstance(cands, set)
