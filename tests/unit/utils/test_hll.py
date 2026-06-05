"""
HyperLogLog单元测试
"""
import pytest
from core.algorithms.hll import HyperLogLog, GlobalHLL


class TestHyperLogLog:
    """测试HyperLogLog基本功能"""
    
    def test_initialization(self):
        """测试初始化"""
        hll = HyperLogLog(b=10)
        assert hll.b == 10
        assert hll.m == 1024  # 2^10
        assert len(hll.registers) == 1024
    
    def test_add_single_item(self):
        """测试添加单个元素"""
        hll = HyperLogLog()
        hll.add("test")
        
        count = hll.count()
        assert count > 0
    
    def test_add_multiple_items(self):
        """测试添加多个元素"""
        hll = HyperLogLog()
        
        for i in range(100):
            hll.add(f"item_{i}")
        
        count = hll.count()
        # 允许一定误差（通常在3%以内）
        assert 90 <= count <= 110, f"估计值 {count} 超出预期范围"
    
    def test_duplicate_items(self):
        """测试重复元素"""
        hll = HyperLogLog()
        
        # 添加相同元素多次
        for _ in range(10):
            hll.add("duplicate")
        
        count = hll.count()
        # 应该只计数1次
        assert count == 1
    
    def test_accuracy_small_set(self):
        """测试小数据集准确性"""
        hll = HyperLogLog(b=10)
        
        n = 100
        for i in range(n):
            hll.add(i)
        
        count = hll.count()
        error_rate = abs(count - n) / n
        assert error_rate < 0.1, f"误差率 {error_rate} 过高"
    
    def test_accuracy_medium_set(self):
        """测试中等数据集准确性"""
        hll = HyperLogLog(b=12)  # 更高精度
        
        n = 10000
        for i in range(n):
            hll.add(i)
        
        count = hll.count()
        error_rate = abs(count - n) / n
        assert error_rate < 0.05, f"误差率 {error_rate} 过高"
    
    def test_accuracy_large_set(self):
        """测试大数据集准确性"""
        hll = HyperLogLog(b=14)  # 高精度
        
        n = 100000
        for i in range(n):
            hll.add(i)
        
        count = hll.count()
        error_rate = abs(count - n) / n
        assert error_rate < 0.02, f"误差率 {error_rate} 过高"
    
    def test_different_data_types(self):
        """测试不同数据类型"""
        hll = HyperLogLog()
        
        hll.add("string")
        hll.add(12345)
        hll.add(3.14)
        hll.add(True)
        hll.add(None)
        
        count = hll.count()
        assert 4 <= count <= 6  # 允许一定误差
    
    def test_empty_hll(self):
        """测试空HLL"""
        hll = HyperLogLog()
        count = hll.count()
        assert count == 0
    
    def test_precision_parameter(self):
        """测试精度参数"""
        hll_low = HyperLogLog(b=8)   # 低精度
        hll_high = HyperLogLog(b=16)  # 高精度
        
        n = 10000
        for i in range(n):
            hll_low.add(i)
            hll_high.add(i)
        
        count_low = hll_low.count()
        count_high = hll_high.count()
        
        error_low = abs(count_low - n) / n
        error_high = abs(count_high - n) / n
        
        # 高精度应该更准确
        assert error_high < error_low


class TestGlobalHLL:
    """测试全局HLL管理器"""
    
    def test_get_hll(self):
        """测试获取HLL"""
        hll1 = GlobalHLL.get_hll("test1")
        hll2 = GlobalHLL.get_hll("test1")
        hll3 = GlobalHLL.get_hll("test2")
        
        # 同名返回同一实例
        assert hll1 is hll2
        # 不同名返回不同实例
        assert hll1 is not hll3
    
    def test_persistent_counting(self):
        """测试持久化计数"""
        hll = GlobalHLL.get_hll("persistent")
        
        # 第一次添加
        for i in range(100):
            hll.add(i)
        
        count1 = hll.count()
        
        # 再次获取同一实例
        hll2 = GlobalHLL.get_hll("persistent")
        
        # 继续添加
        for i in range(100, 200):
            hll2.add(i)
        
        count2 = hll2.count()
        
        # 计数应该累积
        assert count2 > count1


class TestHLLPerformance:
    """测试HLL性能"""
    
    def test_memory_efficiency(self):
        """测试内存效率"""
        import sys
        
        hll = HyperLogLog(b=10)
        
        # 添加大量元素
        for i in range(1000000):
            hll.add(i)
        
        # HLL本身应该很小（只有寄存器数组）
        size = sys.getsizeof(hll.registers)
        assert size < 100000, f"HLL占用内存过大: {size} bytes"
    
    def test_speed(self):
        """测试速度"""
        import time
        
        hll = HyperLogLog()
        
        start = time.time()
        for i in range(100000):
            hll.add(i)
        elapsed = time.time() - start
        
        # 应该很快（<1秒）
        assert elapsed < 1.0, f"处理速度过慢: {elapsed}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
