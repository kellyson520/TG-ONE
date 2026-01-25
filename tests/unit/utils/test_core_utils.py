"""
Utils 核心工具测试
测试 logger_utils, error_handler 等核心工具
"""
import pytest
import logging
from unittest.mock import MagicMock, patch


class TestLoggerUtils:
    """测试日志工具"""
    
    def test_get_logger(self):
        """测试获取 logger"""
        from utils.core.logger_utils import get_logger
        
        logger = get_logger("test_module")
        
        assert logger is not None
        # Logger 可能是 StandardLogger 或 logging.Logger
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'debug')
    
    def test_logger_with_different_names(self):
        """测试不同名称的 logger"""
        from utils.core.logger_utils import get_logger
        
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        # 验证两个 logger 都是有效的
        assert logger1 is not None
        assert logger2 is not None
        
        # 验证它们都有基本的日志方法
        assert hasattr(logger1, 'info')
        assert hasattr(logger1, 'error')
        assert hasattr(logger2, 'info')
        assert hasattr(logger2, 'error')


class TestErrorHandler:
    """测试错误处理装饰器"""
    
    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self):
        """测试 handle_errors 装饰器 - 成功情况"""
        from utils.core.error_handler import handle_errors
        
        @handle_errors(default_return="error")
        async def test_func():
            return "success"
        
        result = await test_func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_handle_errors_decorator_with_exception(self):
        """测试 handle_errors 装饰器 - 异常情况"""
        from utils.core.error_handler import handle_errors
        
        @handle_errors(default_return="error_occurred")
        async def test_func():
            raise ValueError("Test error")
        
        result = await test_func()
        assert result == "error_occurred"


class TestConstants:
    """测试常量定义"""
    
    def test_temp_dir_exists(self):
        """测试 TEMP_DIR 常量存在"""
        from utils.core.constants import TEMP_DIR
        
        assert TEMP_DIR is not None
        assert isinstance(TEMP_DIR, str) or hasattr(TEMP_DIR, '__fspath__')
    
    def test_version_constants(self):
        """测试版本相关常量"""
        try:
            from utils.core.constants import VERSION
            assert VERSION is not None
        except ImportError:
            # VERSION 可能在 version.py 中
            from version import VERSION
            assert VERSION is not None


class TestSettings:
    """测试配置系统"""
    
    def test_settings_import(self):
        """测试配置可以导入"""
        from core.config import settings
        
        assert settings is not None
    
    def test_settings_has_database_url(self):
        """测试配置包含数据库 URL"""
        from core.config import settings
        
        assert hasattr(settings, 'DATABASE_URL')
        assert settings.DATABASE_URL is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
