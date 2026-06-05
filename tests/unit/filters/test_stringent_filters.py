import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.rule.filter import RuleFilterService
from filters.init_filter import InitFilter
from filters.advanced_media_filter import AdvancedMediaFilter
from enums.enums import ForwardMode
from types import SimpleNamespace

# --- 1. RuleFilterService Stringent Tests ---

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
async def test_rule_filter_complex_reverse_logic_overlap():
    """
    测试复杂的反转逻辑重叠：当关键词同时满足多个条件时
    """
    # 场景：白名单模式 + 反转黑名单。
    # 词库：[A(白), B(黑)]
    # 内容包含 A 和 B -> 应该拦截 (因为黑名单词命中)
    rule = MockRule(
        ForwardMode.WHITELIST,
        [MockKeyword("apple", False), MockKeyword("bad", True)],
        enable_reverse_blacklist=True
    )
    assert await RuleFilterService.check_keywords(rule, "i have a bad apple") is False
    assert await RuleFilterService.check_keywords(rule, "i have a good apple") is True

    # 场景：黑名单模式 + 反转白名单。
    # 词库：[A(黑), B(白)]
    # 内容包含 A 和 B -> 应该放行 (因为白名单词豁免)
    rule = MockRule(
        ForwardMode.BLACKLIST,
        [MockKeyword("spam", True), MockKeyword("vip", False)],
        enable_reverse_whitelist=True
    )
    assert await RuleFilterService.check_keywords(rule, "this is spam for vip") is True
    assert await RuleFilterService.check_keywords(rule, "this is spam for casuals") is False

# --- 2. AdvancedMediaFilter Boundary Tests ---

@pytest.mark.asyncio
async def test_adv_media_boundary_size():
    """测试文件大小过滤的边界值"""
    adv_filter = AdvancedMediaFilter()
    rule = MockRule(enable_file_size_range=True, min_file_size=100.0, max_file_size=200.0)
    
    mock_msg = MagicMock()
    with patch("filters.advanced_media_filter.get_media_size", new_callable=AsyncMock) as mock_size:
        # 正好等于最小值 (100KB)
        mock_size.return_value = 100 * 1024
        assert await adv_filter._check_file_size_range_filter(mock_msg, rule) is True
        
        # 正好等于最大值 (200KB)
        mock_size.return_value = 200 * 1024
        assert await adv_filter._check_file_size_range_filter(mock_msg, rule) is True
        
        # 略低于最小值 (99.9KB)
        mock_size.return_value = 99.9 * 1024
        assert await adv_filter._check_file_size_range_filter(mock_msg, rule) is False
        
        # 略高于最大值 (200.1KB)
        mock_size.return_value = 200.1 * 1024
        assert await adv_filter._check_file_size_range_filter(mock_msg, rule) is False

# --- 3. InitFilter Media Group Key Isolation ---

@pytest.mark.asyncio
async def test_init_filter_cache_isolation():
    """测试相同 grouped_id 在不同会话中的隔离性"""
    init_filter = InitFilter()
    
    # 两个上下文，相同的 grouped_id 但不同的 chat_id
    ctx1 = SimpleNamespace(
        rule=SimpleNamespace(), 
        event=MagicMock(), 
        errors=[], 
        dup_signatures=[], 
        chat_id=111,
        message_text=None,
        buttons=None,
        metadata={},
        is_media_group=False
    )
    ctx1.event.message.grouped_id = 999
    ctx1.event.chat_id = 111
    ctx1.event.client = AsyncMock()
    
    ctx2 = SimpleNamespace(
        rule=SimpleNamespace(), 
        event=MagicMock(), 
        errors=[], 
        dup_signatures=[], 
        chat_id=222,
        message_text=None,
        buttons=None,
        metadata={},
        is_media_group=False
    )
    ctx2.event.message.grouped_id = 999
    ctx2.event.chat_id = 222
    ctx2.event.client = AsyncMock()

    # 模拟 ctx1 执行并存入缓存
    msg1 = MagicMock(grouped_id=999, text="caption 111")
    async def iter_msg1(*args, **kwargs):
        yield msg1
    ctx1.event.client.iter_messages = iter_msg1
    
    # 模拟 ctx2 执行并存入缓存
    msg2 = MagicMock(grouped_id=999, text="caption 222")
    async def iter_msg2(*args, **kwargs):
        yield msg2
    ctx2.event.client.iter_messages = iter_msg2

    from core.cache.unified_cache import get_smart_cache
    cache = get_smart_cache("media_group")
    
    # 清理可能存在的缓存干扰
    cache.delete("media_group_ctx:111:999")
    cache.delete("media_group_ctx:222:999")

    # 执行 ctx1
    await init_filter._process(ctx1)
    assert ctx1.message_text == "caption 111"
    
    # 执行 ctx2
    await init_filter._process(ctx2)
    assert ctx2.message_text == "caption 222" # 如果不带 chat_id，这里会命中 111 的缓存变成 "caption 111"

# --- 4. Signature Collision Test ---

@pytest.mark.asyncio
async def test_signature_collision_mitigation():
    """测试增加 chat_id 后对签名碰撞的防护"""
    from services.media_service import extract_message_signature
    
    # 模拟两个会话中 ID 相同的消息，且无 media_id (触发 fallback)
    msg1 = MagicMock(chat_id=1001, id=555, document=None, video=None)
    msg1.photo = MagicMock(id=None)
    
    msg2 = MagicMock(chat_id=2002, id=555, document=None, video=None)
    msg2.photo = MagicMock(id=None)
    
    sig1, _ = extract_message_signature(msg1)
    sig2, _ = extract_message_signature(msg2)
    
    # 之前 sig1 == sig2 == "photo:1001_555" (假想的碰撞)
    # 现在应该是 "photo:1001_555" 和 "photo:2002_555"
    assert sig1 != sig2
    assert "1001_555" in sig1
    assert "2002_555" in sig2
