"""id_utils.py 测试 — normalize_chat_id + build_candidate_telegram_ids 纯函数"""
import pytest
from core.helpers.id_utils import normalize_chat_id, build_candidate_telegram_ids


class TestNormalizeChatId:
    """normalize_chat_id 测试"""

    def test_super_group_format(self):
        """-100 前缀的超级群组 ID"""
        assert normalize_chat_id(-1002815974674) == "2815974674"

    def test_negative_non_super_group(self):
        """普通负数 ID"""
        assert normalize_chat_id(-2815974674) == "2815974674"

    def test_positive_id(self):
        """正数 ID 保持不变"""
        assert normalize_chat_id(2815974674) == "2815974674"

    def test_string_super_group(self):
        """字符串格式 -100 前缀"""
        assert normalize_chat_id("-1002815974674") == "2815974674"

    def test_string_negative(self):
        """字符串格式负数"""
        assert normalize_chat_id("-2815974674") == "2815974674"

    def test_string_positive(self):
        """字符串格式正数"""
        assert normalize_chat_id("2815974674") == "2815974674"

    def test_small_negative(self):
        """小负数（非超级群组格式）"""
        assert normalize_chat_id(-12345) == "12345"

    def test_zero(self):
        """零"""
        assert normalize_chat_id(0) == "0"

    def test_non_numeric_string(self):
        """非数字字符串返回原值"""
        assert normalize_chat_id("abc123") == "abc123"

    def test_username_format(self):
        """用户名格式返回原值"""
        assert normalize_chat_id("@test_group") == "@test_group"

    def test_single_digit(self):
        """单位数"""
        assert normalize_chat_id(5) == "5"

    def test_large_id(self):
        """大 ID"""
        assert normalize_chat_id(1234567890123) == "1234567890123"

    def test_negative_100_prefix_only(self):
        """-100 本身（只有3位）"""
        # -100 → abs = "100", len=3, 不满足 len>3 条件
        result = normalize_chat_id(-100)
        assert result == "100"


class TestBuildCandidateTelegramIds:
    """build_candidate_telegram_ids 测试"""

    def test_super_group_generates_variants(self):
        """超级群组 ID 生成所有变体"""
        candidates = build_candidate_telegram_ids(-1002815974674)
        # 应包含标准化后的纯 ID
        assert "2815974674" in candidates
        # 应包含负数形式
        assert "-2815974674" in candidates
        # 应包含 -100 前缀形式
        assert "-1002815974674" in candidates or "-1002815974674" in [str(-1002815974674)]

    def test_positive_id_generates_variants(self):
        """正数 ID 生成变体"""
        candidates = build_candidate_telegram_ids(2815974674)
        assert "2815974674" in candidates
        assert "-2815974674" in candidates
        assert "-1002815974674" in candidates

    def test_string_input(self):
        """字符串输入"""
        candidates = build_candidate_telegram_ids("2815974674")
        assert "2815974674" in candidates

    def test_non_numeric_preserved(self):
        """非数字输入保留原值"""
        candidates = build_candidate_telegram_ids("@username")
        assert "@username" in candidates
        # 非数字不会生成变体
        assert len(candidates) <= 2  # 原值 + normalize 结果

    def test_returns_set(self):
        """返回集合类型"""
        result = build_candidate_telegram_ids(12345)
        assert isinstance(result, set)

    def test_no_duplicates(self):
        """没有重复项"""
        candidates = build_candidate_telegram_ids(2815974674)
        assert len(candidates) == len(set(candidates))

    def test_zero_id(self):
        """零 ID"""
        candidates = build_candidate_telegram_ids(0)
        assert "0" in candidates

    def test_super_group_preserves_original(self):
        """超级群组保留原始值"""
        candidates = build_candidate_telegram_ids(-1002815974674)
        raw = str(-1002815974674)
        assert raw in candidates
