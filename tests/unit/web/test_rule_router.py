"""
Web 模块单元测试 - Rule Router

测试 rule_router.py 中的新增端点
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI

# 创建测试用 app
app = FastAPI()


@pytest.fixture
def mock_user():
    """模拟登录用户"""
    user = MagicMock()
    user.id = 1
    user.username = "admin"
    user.is_admin = True
    return user


@pytest.fixture
def mock_rule():
    """模拟规则对象"""
    rule = MagicMock()
    rule.id = 1
    rule.source_chat_id = 100
    rule.target_chat_id = 200
    rule.enable_rule = True
    rule.enable_dedup = False
    rule.forward_mode = MagicMock(value="BLACKLIST")
    rule.use_bot = True
    rule.message_mode = MagicMock(value="MARKDOWN")
    rule.is_replace = False
    rule.is_preview = MagicMock(value="FOLLOW")
    rule.is_original_link = False
    rule.is_delete_original = False
    rule.is_original_sender = False
    rule.is_original_time = False
    rule.force_pure_forward = False
    rule.enable_delay = False
    rule.delay_seconds = 5
    rule.max_media_size = 10
    rule.enable_media_size_filter = False
    rule.enable_media_type_filter = False
    rule.is_ai = False
    rule.ai_model = None
    rule.ai_prompt = None
    rule.description = "Test rule"
    rule.priority = 0
    rule.created_at = "2026-01-11T00:00:00"
    rule.updated_at = "2026-01-11T00:00:00"
    rule.message_count = 100
    
    # 关联对象
    rule.source_chat = MagicMock()
    rule.source_chat.id = 100
    rule.source_chat.name = "Source Chat"
    rule.source_chat.telegram_chat_id = "-1001234567890"
    rule.source_chat.username = "source_chat"
    
    rule.target_chat = MagicMock()
    rule.target_chat.id = 200
    rule.target_chat.name = "Target Chat"
    rule.target_chat.telegram_chat_id = "-1009876543210"
    rule.target_chat.username = "target_chat"
    
    # 关键字和替换规则
    kw1 = MagicMock()
    kw1.id = 1
    kw1.keyword = "test"
    kw1.is_regex = False
    kw1.is_blacklist = False
    rule.keywords = [kw1]
    
    rr1 = MagicMock()
    rr1.id = 1
    rr1.pattern = "old"
    rr1.content = "new"
    rule.replace_rules = [rr1]
    
    return rule


class TestRuleRouterGetDetail:
    """测试 GET /api/rules/{rule_id} 端点"""
    
    @pytest.mark.asyncio
    async def test_get_rule_detail_success(self, mock_rule, mock_user):
        """测试成功获取规则详情"""
        from web_admin.routers.rules.rule_crud_router import get_rule_detail
        
        # Mock 依赖
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_rule)
        
        mock_stats_repo = MagicMock()
        mock_stats_repo.get_rules_stats_batch = AsyncMock(return_value={})
        
        # 调用端点
        response = await get_rule_detail(
            rule_id=1, 
            user=mock_user,
            rule_repo=mock_repo,
            stats_repo=mock_stats_repo
        )
        
        # 验证
        assert response.success is True
        assert response.data is not None
        assert response.data['id'] == 1
    
    @pytest.mark.asyncio
    async def test_get_rule_detail_not_found(self, mock_user):
        """测试规则不存在"""
        from web_admin.routers.rules.rule_crud_router import get_rule_detail
        
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        
        mock_stats_repo = MagicMock()
        
        response = await get_rule_detail(
            rule_id=999, 
            user=mock_user, 
            rule_repo=mock_repo,
            stats_repo=mock_stats_repo
        )
        
        assert response.success is False
        assert response.error == '规则不存在'


class TestRuleRouterUpdate:
    """测试 PUT /api/rules/{rule_id} 端点"""
    
    @pytest.mark.asyncio
    async def test_update_rule_success(self, mock_user):
        """测试成功更新规则"""
        from web_admin.routers.rules.rule_crud_router import update_rule
        from web_admin.schemas.rule_schemas import RuleUpdateRequest
        
        payload = RuleUpdateRequest(
            enabled=False,
            enable_dedup=True,
            description="Updated description"
        )
        
        mock_service = MagicMock()
        mock_service.update_rule = AsyncMock(return_value={'success': True})
        
        response = await update_rule(
            rule_id=1, 
            payload=payload, 
            user=mock_user,
            service=mock_service
        )
        
        assert response.success is True
        assert response.message == '规则更新成功'
        mock_service.update_rule.assert_called_once()
        call_kwargs = mock_service.update_rule.call_args[1]
        assert call_kwargs['enable_rule'] == False
        assert call_kwargs['enable_dedup'] == True
        assert call_kwargs['description'] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_update_rule_no_changes(self, mock_user):
        """测试无更新项"""
        from web_admin.routers.rules.rule_crud_router import update_rule
        from web_admin.schemas.rule_schemas import RuleUpdateRequest
        
        payload = RuleUpdateRequest()  # 空请求
        mock_service = MagicMock()
        
        response = await update_rule(
            rule_id=1, 
            payload=payload, 
            user=mock_user,
            service=mock_service
        )
        
        assert response.success is True
        assert response.message == '没有更新项'


class TestRuleRouterKeywords:
    """测试关键字相关端点"""
    
    @pytest.mark.asyncio
    async def test_add_keywords_success(self, mock_user):
        """测试添加关键字"""
        from web_admin.routers.rules.rule_content_router import add_keywords
        from web_admin.schemas.rule_schemas import KeywordAddRequest
        
        payload = KeywordAddRequest(
            keywords=["keyword1", "keyword2"],
            is_regex=False,
            is_negative=False
        )
        
        mock_service = MagicMock()
        mock_service.add_keywords = AsyncMock(return_value={'success': True, 'count': 2})
        
        response = await add_keywords(
            rule_id=1, 
            payload=payload, 
            user=mock_user,
            service=mock_service
        )
        
        assert response.success is True
        assert response.message == "成功添加 2 个关键字"


class TestRuleRouterReplaceRules:
    """测试替换规则相关端点"""
    
    @pytest.mark.asyncio
    async def test_add_replace_rules_success(self, mock_user):
        """测试添加替换规则"""
        from web_admin.routers.rules.rule_content_router import add_replace_rules
        from web_admin.schemas.rule_schemas import ReplaceRuleAddRequest
        
        payload = ReplaceRuleAddRequest(
            pattern="old_text",
            replacement="new_text",
            is_regex=False
        )
        
        mock_service = MagicMock()
        mock_service.add_replace_rules = AsyncMock(return_value={'success': True})
        
        response = await add_replace_rules(
            rule_id=1, 
            payload=payload, 
            user=mock_user,
            service=mock_service
        )
        
        assert response.success is True
