"""rule_utils 测试 — 转发规则工具函数"""
import pytest
from unittest.mock import MagicMock, PropertyMock
from core.helpers.rule_utils import extract_rule_info, is_rule_enabled, should_use_bot, get_rule_id


def _make_rule(**attrs):
    """创建 mock ForwardRule"""
    rule = MagicMock(spec=[])
    for k, v in attrs.items():
        setattr(rule, k, v)
    return rule


class TestExtractRuleInfo:
    """extract_rule_info 测试"""

    def test_basic_rule(self):
        rule = _make_rule(
            id=1, enable_rule=True, use_bot=False,
            source_chat_id=100, target_chat_id=200,
        )
        info = extract_rule_info(rule)
        assert info["id"] == 1
        assert info["enable_rule"] is True
        assert info["use_bot"] is False
        assert info["source_chat_id"] == 100
        assert info["target_chat_id"] == 200

    def test_with_source_chat_name(self):
        source_chat = MagicMock()
        source_chat.name = "源频道"
        rule = _make_rule(id=2, source_chat=source_chat)
        info = extract_rule_info(rule)
        assert info["source_chat_name"] == "源频道"

    def test_with_target_chat_name(self):
        target_chat = MagicMock()
        target_chat.name = "目标频道"
        rule = _make_rule(id=3, target_chat=target_chat)
        info = extract_rule_info(rule)
        assert info["target_chat_name"] == "目标频道"

    def test_defaults_when_no_attrs(self):
        rule = _make_rule()
        info = extract_rule_info(rule)
        assert info["id"] is None
        assert info["enable_rule"] is False
        assert info["source_chat_name"] == "未知"
        assert info["target_chat_name"] == "未知"

    def test_exception_on_chat_access(self):
        """关联对象访问异常不影响返回"""
        rule = MagicMock(spec=[])
        rule.id = 1
        type(rule).source_chat = property(lambda self: (_ for _ in ()).throw(RuntimeError("detached")))
        info = extract_rule_info(rule)
        assert info["id"] == 1
        assert info["source_chat_name"] == "未知"

    def test_none_rule(self):
        """None 输入"""
        # getattr(None, 'id', None) 不会抛异常
        info = extract_rule_info(None)
        assert info["id"] is None


class TestIsRuleEnabled:
    """is_rule_enabled 测试"""

    def test_enabled(self):
        rule = _make_rule(enable_rule=True)
        assert is_rule_enabled(rule) is True

    def test_disabled(self):
        rule = _make_rule(enable_rule=False)
        assert is_rule_enabled(rule) is False

    def test_missing_attr(self):
        rule = _make_rule()
        assert is_rule_enabled(rule) is False

    def test_truthy_value(self):
        rule = _make_rule(enable_rule=1)
        assert is_rule_enabled(rule) is True


class TestShouldUseBot:
    """should_use_bot 测试"""

    def test_use_bot_true(self):
        rule = _make_rule(use_bot=True)
        assert should_use_bot(rule) is True

    def test_use_bot_false(self):
        rule = _make_rule(use_bot=False)
        assert should_use_bot(rule) is False

    def test_missing_attr(self):
        rule = _make_rule()
        assert should_use_bot(rule) is False


class TestGetRuleId:
    """get_rule_id 测试"""

    def test_normal_id(self):
        rule = _make_rule(id=42)
        assert get_rule_id(rule) == 42

    def test_none_id(self):
        rule = _make_rule(id=None)
        assert get_rule_id(rule) is None

    def test_missing_id(self):
        rule = _make_rule()
        assert get_rule_id(rule) is None

    def test_string_id(self):
        rule = _make_rule(id="abc")
        assert get_rule_id(rule) == "abc"
