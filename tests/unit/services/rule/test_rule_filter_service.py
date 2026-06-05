import pytest
from unittest.mock import MagicMock
from services.rule.filter import RuleFilterService
from enums.enums import ForwardMode

class MockKeyword:
    def __init__(self, keyword, is_blacklist=True, is_regex=False):
        self.keyword = keyword
        self.is_blacklist = is_blacklist
        self.is_regex = is_regex

class MockRule:
    def __init__(self, forward_mode=ForwardMode.BLACKLIST, keywords=None, **kwargs):
        self.forward_mode = forward_mode
        self.keywords = keywords or []
        self.id = 1
        for k, v in kwargs.items():
            setattr(self, k, v)

@pytest.mark.asyncio
async def test_whitelist_mode_standard():
    # 纯白名单：内容不在白名单中，拦截
    rule = MockRule(ForwardMode.WHITELIST, [MockKeyword("apple", is_blacklist=False)])
    assert await RuleFilterService.check_keywords(rule, "orange") is False
    
    # 纯白名单：内容在白名单中，放行
    assert await RuleFilterService.check_keywords(rule, "i love apple") is True

@pytest.mark.asyncio
async def test_whitelist_mode_reverse_blacklist():
    # 白名单+反转黑名单：内容在白名单，但同时包含黑名单内容，拦截（即：排除干扰项）
    rule = MockRule(
        ForwardMode.WHITELIST, 
        [
            MockKeyword("apple", is_blacklist=False),
            MockKeyword("bad", is_blacklist=True)
        ],
        enable_reverse_blacklist=True
    )
    # 命中白名单，未命中黑名单 -> 放行
    assert await RuleFilterService.check_keywords(rule, "good apple") is True
    # 命中白名单，命中黑名单 -> 拦截
    assert await RuleFilterService.check_keywords(rule, "bad apple") is False

@pytest.mark.asyncio
async def test_blacklist_mode_standard():
    # 纯黑名单：命中黑名单，拦截
    rule = MockRule(ForwardMode.BLACKLIST, [MockKeyword("spam", is_blacklist=True)])
    assert await RuleFilterService.check_keywords(rule, "this is spam") is False
    # 纯黑名单：未命中黑名单，放行
    assert await RuleFilterService.check_keywords(rule, "hello") is True

@pytest.mark.asyncio
async def test_blacklist_mode_reverse_whitelist():
    # 黑名单+反转白名单：命中黑名单，但同时包含白名单内容（特权词），豁免拦截
    rule = MockRule(
        ForwardMode.BLACKLIST,
        [
            MockKeyword("spam", is_blacklist=True),
            MockKeyword("vip", is_blacklist=False)
        ],
        enable_reverse_whitelist=True
    )
    # 命中黑名单，无白名单词 -> 拦截
    assert await RuleFilterService.check_keywords(rule, "buy spam now") is False
    # 命中黑名单，有白名单词 -> 豁免，放行
    assert await RuleFilterService.check_keywords(rule, "vip spam content") is True

@pytest.mark.asyncio
async def test_mixed_mode_whitelist_then_blacklist():
    rule = MockRule(
        ForwardMode.WHITELIST_THEN_BLACKLIST,
        [
            MockKeyword("apple", is_blacklist=False),
            MockKeyword("frozen", is_blacklist=True)
        ]
    )
    # 不在白名单 -> 拦截
    assert await RuleFilterService.check_keywords(rule, "banana") is False
    # 在白名单，不在黑名单 -> 放行
    assert await RuleFilterService.check_keywords(rule, "fresh apple") is True
    # 在白名单，但在黑名单 -> 拦截
    assert await RuleFilterService.check_keywords(rule, "frozen apple") is False

@pytest.mark.asyncio
async def test_mixed_mode_blacklist_then_whitelist():
    rule = MockRule(
        ForwardMode.BLACKLIST_THEN_WHITELIST,
        [
            MockKeyword("spam", is_blacklist=True),
            MockKeyword("free", is_blacklist=False)
        ]
    )
    # 命中黑名单 -> 拦截
    assert await RuleFilterService.check_keywords(rule, "get spam") is False
    # 未命黑名单，但不在白名单 -> 拦截
    assert await RuleFilterService.check_keywords(rule, "hello") is False
    # 未命中黑名单，且命中白名单 -> 放行
    assert await RuleFilterService.check_keywords(rule, "free gift") is True

@pytest.mark.asyncio
async def test_regex_keywords():
    rule = MockRule(
        ForwardMode.BLACKLIST,
        [MockKeyword(r"s[p4]am", is_blacklist=True, is_regex=True)]
    )
    assert await RuleFilterService.check_keywords(rule, "get s4am") is False
    assert await RuleFilterService.check_keywords(rule, "normal text") is True

@pytest.mark.asyncio
async def test_case_insensitivity():
    rule = MockRule(
        ForwardMode.WHITELIST,
        [MockKeyword("APPLE", is_blacklist=False)]
    )
    # AC 自动机和正则都应支持大小写忽略
    assert await RuleFilterService.check_keywords(rule, "apple") is True
