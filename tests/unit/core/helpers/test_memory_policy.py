"""memory_policy 测试 — 内存阈值动态计算"""
import pytest
from core.helpers.memory_policy import _coerce_positive_number, resolve_process_memory_thresholds


class TestCoercePositiveNumber:
    """_coerce_positive_number 测试"""

    def test_positive_int(self):
        assert _coerce_positive_number(100) == 100.0

    def test_positive_float(self):
        assert _coerce_positive_number(3.14) == 3.14

    def test_zero_returns_none(self):
        assert _coerce_positive_number(0) is None

    def test_negative_returns_none(self):
        assert _coerce_positive_number(-5) is None

    def test_bool_returns_none(self):
        """bool 不是有效数字"""
        assert _coerce_positive_number(True) is None
        assert _coerce_positive_number(False) is None

    def test_string_returns_none(self):
        assert _coerce_positive_number("100") is None

    def test_none_returns_none(self):
        assert _coerce_positive_number(None) is None


class TestResolveThresholds:
    """resolve_process_memory_thresholds 测试"""

    def test_with_total_memory(self):
        """提供 total_memory_bytes 计算动态阈值"""
        # 1GB = 1024*1024*1024 bytes
        total_1gb = 1024 * 1024 * 1024
        w, c = resolve_process_memory_thresholds(2048, 3072, total_memory_bytes=total_1gb)
        # 1024MB * 0.45 = 460, max(256, 460) = 460
        assert w == 460
        # 1024MB * 0.70 = 716, max(460+128, 716) = 716
        assert c == 716

    def test_small_memory_clamped(self):
        """小内存时动态值可能低于配置值，取较小值"""
        # 256MB total
        total_256mb = 256 * 1024 * 1024
        w, c = resolve_process_memory_thresholds(512, 768, total_memory_bytes=total_256mb)
        # 256 * 0.45 = 115, max(256, 115) = 256
        # min(512, 256) = 256
        assert w == 256

    def test_critical_always_greater_than_warning(self):
        """critical 始终大于 warning"""
        w, c = resolve_process_memory_thresholds(100, 100, total_memory_bytes=1024*1024*1024)
        assert c > w

    def test_zero_total_memory_fallback(self):
        """total_memory=0 回退到配置值"""
        w, c = resolve_process_memory_thresholds(512, 1024, total_memory_bytes=0)
        assert w == 512
        assert c == 1024

    def test_none_total_memory_no_psutil(self):
        """不传 total_memory_bytes 时尝试 psutil"""
        # 如果 psutil 不可用也回退到配置值
        w, c = resolve_process_memory_thresholds(512, 1024)
        # 结果取决于环境，但不应抛异常
        assert isinstance(w, int)
        assert isinstance(c, int)

    def test_large_memory(self):
        """大内存服务器"""
        # 16GB
        total_16gb = 16 * 1024 * 1024 * 1024
        w, c = resolve_process_memory_thresholds(8192, 12288, total_memory_bytes=total_16gb)
        # 16384 * 0.45 = 7372, max(256, 7372) = 7372
        # min(8192, 7372) = 7372
        assert w == 7372

    def test_returns_ints(self):
        """返回值始终是 int"""
        w, c = resolve_process_memory_thresholds(512, 1024, total_memory_bytes=1024*1024*1024)
        assert isinstance(w, int)
        assert isinstance(c, int)

    def test_negative_total_memory_fallback(self):
        """负数 total_memory 回退到配置值"""
        w, c = resolve_process_memory_thresholds(512, 1024, total_memory_bytes=-1)
        assert w == 512
        assert c == 1024
