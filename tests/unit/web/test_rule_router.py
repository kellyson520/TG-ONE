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
        from web_admin.routers.rule_router import get_rule_detail
        from core.container import container
        
        # Mock 依赖
        with patch.object(container.rule_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_rule
            
            # 调用端点
            response = await get_rule_detail(rule_id=1, user=mock_user)
            
            # 验证
            assert response.status_code == 200
            data = response.body.decode()
            assert '"success": true' in data or '"success":true' in data
            assert '"id": 1' in data or '"id":1' in data
    
    @pytest.mark.asyncio
    async def test_get_rule_detail_not_found(self, mock_user):
        """测试规则不存在"""
        from web_admin.routers.rule_router import get_rule_detail
        from core.container import container
        
        with patch.object(container.rule_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            response = await get_rule_detail(rule_id=999, user=mock_user)
            
            assert response.status_code == 404
            data = response.body.decode()
            assert '"success": false' in data or '"success":false' in data


class TestRuleRouterUpdate:
    """测试 PUT /api/rules/{rule_id} 端点"""
    
    @pytest.mark.asyncio
    async def test_update_rule_success(self, mock_user):
        """测试成功更新规则"""
        from web_admin.routers.rule_router import update_rule, RuleUpdateRequest
        from core.container import container
        
        payload = RuleUpdateRequest(
            enabled=False,
            enable_dedup=True,
            description="Updated description"
        )
        
        with patch.object(container.rule_management_service, 'update_rule', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {'success': True}
            
            response = await update_rule(rule_id=1, payload=payload, user=mock_user)
            
            assert response.status_code == 200
            mock_update.assert_called_once()
            call_kwargs = mock_update.call_args[1]
            assert call_kwargs['enable_rule'] == False
            assert call_kwargs['enable_dedup'] == True
            assert call_kwargs['description'] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_update_rule_no_changes(self, mock_user):
        """测试无更新项"""
        from web_admin.routers.rule_router import update_rule, RuleUpdateRequest
        
        payload = RuleUpdateRequest()  # 空请求
        
        response = await update_rule(rule_id=1, payload=payload, user=mock_user)
        
        assert response.status_code == 200
        data = response.body.decode()
        assert '没有更新项' in data


class TestRuleRouterKeywords:
    """测试关键字相关端点"""
    
    @pytest.mark.asyncio
    async def test_add_keywords_success(self, mock_user):
        """测试添加关键字"""
        from web_admin.routers.rule_router import add_keywords, KeywordAddRequest
        from core.container import container
        
        payload = KeywordAddRequest(
            keywords=["keyword1", "keyword2"],
            is_regex=False,
            is_negative=False
        )
        
        with patch.object(container.rule_management_service, 'add_keywords', new_callable=AsyncMock) as mock_add:
            mock_add.return_value = {'success': True, 'count': 2}
            
            response = await add_keywords(rule_id=1, payload=payload, user=mock_user)
            
            assert response.status_code == 200
            data = response.body.decode()
            assert '"success": true' in data or '"success":true' in data


class TestRuleRouterReplaceRules:
    """测试替换规则相关端点"""
    
    @pytest.mark.asyncio
    async def test_add_replace_rules_success(self, mock_user):
        """测试添加替换规则"""
        from web_admin.routers.rule_router import add_replace_rules, ReplaceRuleAddRequest
        from core.container import container
        
        payload = ReplaceRuleAddRequest(
            pattern="old_text",
            replacement="new_text",
            is_regex=False
        )
        
        with patch.object(container.rule_management_service, 'add_replace_rules', new_callable=AsyncMock) as mock_add:
            mock_add.return_value = {'success': True}
            
            response = await add_replace_rules(rule_id=1, payload=payload, user=mock_user)
            
            assert response.status_code == 200
            data = response.body.decode()
            assert '"success": true' in data or '"success":true' in data
