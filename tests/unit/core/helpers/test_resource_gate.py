"""resource_gate 测试 — 内存安全检查"""
import pytest
from unittest.mock import patch, MagicMock
from core.helpers.resource_gate import ResourceGate


class TestGetMemoryUsage:
    """get_current_memory_usage 测试"""

    def test_returns_int(self):
        result = ResourceGate.get_current_memory_usage()
        assert isinstance(result, int)

    def test_returns_non_negative(self):
        result = ResourceGate.get_current_memory_usage()
        assert result >= 0


class TestCheckMemorySafe:
    """check_memory_safe 测试"""

    def test_safe_when_under_limit(self):
        """当前内存低于限制"""
        with patch.object(ResourceGate, 'get_current_memory_usage', return_value=100*1024*1024):
            assert ResourceGate.check_memory_safe(limit_bytes=500*1024*1024) is True

    def test_unsafe_when_over_limit(self):
        """当前内存超过限制"""
        with patch.object(ResourceGate, 'get_current_memory_usage', return_value=800*1024*1024):
            assert ResourceGate.check_memory_safe(limit_bytes=500*1024*1024) is False

    def test_safe_when_usage_zero(self):
        """psutil 不可用时返回 0 → 视为安全"""
        with patch.object(ResourceGate, 'get_current_memory_usage', return_value=0):
            assert ResourceGate.check_memory_safe() is True

    def test_exact_limit_is_safe(self):
        """恰好等于限制视为安全"""
        limit = 500 * 1024 * 1024
        with patch.object(ResourceGate, 'get_current_memory_usage', return_value=limit):
            # check 是 current > limit，等于不算超过
            assert ResourceGate.check_memory_safe(limit_bytes=limit) is True

    def test_one_byte_over_is_unsafe(self):
        """超过 1 byte 就是不安全"""
        limit = 500 * 1024 * 1024
        with patch.object(ResourceGate, 'get_current_memory_usage', return_value=limit+1):
            assert ResourceGate.check_memory_safe(limit_bytes=limit) is False


class TestEnforceMemoryLimit:
    """enforce_memory_limit 测试"""

    def test_no_error_when_safe(self):
        """安全时不抛异常"""
        with patch.object(ResourceGate, 'check_memory_safe', return_value=True):
            ResourceGate.enforce_memory_limit()  # 不应抛异常

    def test_raises_when_unsafe(self):
        """超限时抛 MemoryError"""
        with patch.object(ResourceGate, 'check_memory_safe', return_value=False):
            with patch.object(ResourceGate, 'get_current_memory_usage', return_value=900*1024*1024):
                with patch.object(ResourceGate, '_configured_limit_bytes', return_value=500*1024*1024):
                    with pytest.raises(MemoryError, match="exceeded"):
                        ResourceGate.enforce_memory_limit()


class TestDefaultLimit:
    """默认限制测试"""

    def test_default_max_ram_bytes(self):
        """默认限制 768MB"""
        assert ResourceGate.DEFAULT_MAX_RAM_BYTES == 768 * 1024 * 1024

    def test_configured_limit_fallback(self):
        """配置加载失败时回退到默认值"""
        with patch('core.helpers.resource_gate.resolve_process_memory_thresholds', side_effect=Exception("no config")):
            limit = ResourceGate._configured_limit_bytes()
            assert limit == ResourceGate.DEFAULT_MAX_RAM_BYTES
