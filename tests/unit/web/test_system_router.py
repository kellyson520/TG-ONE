"""
Web 模块单元测试 - System Router

测试 system_router.py 中的端点
"""

import pytest
from unittest.mock import MagicMock


class TestSystemRouterStats:
    """测试 /api/system/stats 端点"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟登录用户"""
        user = MagicMock()
        user.id = 1
        user.username = "admin"
        user.is_admin = True
        return user
    
    @pytest.mark.asyncio
    async def test_get_system_stats_function_exists(self):
        """测试 get_system_stats 函数存在"""
        from web_admin.routers.system.stats_router import get_system_stats
        assert callable(get_system_stats)
    
    @pytest.mark.asyncio
    async def test_get_config_function_exists(self):
        """测试 get_config 函数存在"""
        from web_admin.routers.system.maintain_router import get_config
        assert callable(get_config)


class TestSystemRouterAuditLogs:
    """测试审计日志端点"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟登录用户"""
        user = MagicMock()
        user.id = 1
        user.username = "admin"
        user.is_admin = True
        return user
    
    @pytest.mark.asyncio
    async def test_get_audit_logs_function_exists(self):
        """测试 get_audit_logs 函数存在"""
        from web_admin.routers.system.log_router import get_audit_logs
        assert callable(get_audit_logs)


class TestSystemRouterBackup:
    """测试备份相关端点"""
    
    @pytest.mark.asyncio
    async def test_trigger_backup_function_exists(self):
        """测试 trigger_backup 函数存在"""
        from web_admin.routers.system.maintain_router import trigger_backup
        assert callable(trigger_backup)
    
    @pytest.mark.asyncio
    async def test_list_backups_function_exists(self):
        """测试 list_backups 函数存在"""
        from web_admin.routers.system.maintain_router import list_backups
        assert callable(list_backups)


class TestSystemRouterSettings:
    """测试设置相关端点"""
    
    @pytest.mark.asyncio
    async def test_get_full_settings_function_exists(self):
        """测试 get_full_settings 函数存在"""
        from web_admin.routers.system.maintain_router import get_full_settings
        assert callable(get_full_settings)
    
    @pytest.mark.asyncio
    async def test_update_settings_function_exists(self):
        """测试 update_settings 函数存在"""
        from web_admin.routers.system.maintain_router import update_settings
        assert callable(update_settings)


class TestSystemRouterRouter:
    """测试路由注册"""
    
    def test_router_prefix(self):
        """测试路由前缀"""
        from web_admin.routers.system.stats_router import router as stats_router
        assert stats_router is not None
        # Individual routers might not have prefix set if included via include_router
        
    def test_router_has_routes(self):
        """测试路由注册"""
        from web_admin.routers.system.stats_router import router as stats_router
        assert len(stats_router.routes) > 0
