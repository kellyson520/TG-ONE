"""
布隆过滤器单元测试
"""
import pytest
from utils.processing.bloom_filter import BloomFilter, GlobalBloomFilter


class TestBloomFilter:
    """测试布隆过滤器基本功能"""
    
    def test_initialization(self):
        """测试初始化"""
        bf = BloomFilter(capacity=1000, error_rate=0.01)
        assert bf.capacity == 1000
        assert bf.error_rate == 0.01
        assert bf.count == 0
    
    def test_add_and_contains(self):
        """测试添加和查询"""
        bf = BloomFilter(capacity=100, error_rate=0.01)
        
        # 添加元素
        bf.add("test1")
        bf.add("test2")
        bf.add(12345)
        
        # 检查存在性
        assert "test1" in bf
        assert "test2" in bf
        assert 12345 in bf
        
        # 检查不存在的元素
        assert "test3" not in bf
        assert 99999 not in bf
    
    def test_false_positive_rate(self):
        """测试假阳性率（统计测试）"""
        bf = BloomFilter(capacity=1000, error_rate=0.01)
        
        # 添加1000个元素
        for i in range(1000):
            bf.add(f"item_{i}")
        
        # 测试10000个不存在的元素
        false_positives = 0
        test_count = 10000
        for i in range(1000, 1000 + test_count):
            if f"item_{i}" in bf:
                false_positives += 1
        
        # 假阳性率应该接近设定值（允许一定误差）
        actual_rate = false_positives / test_count
        assert actual_rate < 0.05, f"假阳性率过高: {actual_rate}"
    
    def test_empty_filter(self):
        """测试空过滤器"""
        bf = BloomFilter()
        assert "anything" not in bf
    
    def test_duplicate_add(self):
        """测试重复添加"""
        bf = BloomFilter()
        bf.add("test")
        bf.add("test")
        bf.add("test")
        
        assert "test" in bf
        assert bf.count == 3  # 计数会增加


class TestGlobalBloomFilter:
    """测试全局布隆过滤器管理器"""
    
    def test_get_filter(self):
        """测试获取过滤器"""
        bf1 = GlobalBloomFilter.get_filter("test1")
        bf2 = GlobalBloomFilter.get_filter("test1")
        bf3 = GlobalBloomFilter.get_filter("test2")
        
        # 同名返回同一实例
        assert bf1 is bf2
        # 不同名返回不同实例
        assert bf1 is not bf3
    
    def test_clear(self):
        """测试清理"""
        GlobalBloomFilter.get_filter("temp1")
        GlobalBloomFilter.get_filter("temp2")
        
        GlobalBloomFilter.clear()
        
        # 清理后应该创建新实例
        bf_new = GlobalBloomFilter.get_filter("temp1")
        assert bf_new is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
