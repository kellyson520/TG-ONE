import hashlib
import math
import os
import pickle
import logging
from typing import List, Any, Optional

logger = logging.getLogger(__name__)

class BloomFilter:
    """
    高性能布隆过滤器 (高性能纯 Python 实现)
    
    特性:
    - 使用 bytearray 最小化内存占用 (1GB VPS 友好)
    - 使用 Double Hashing (MD5 + SHA1) 优化哈希分布
    - 支持持久化 (Save/Load)
    - 针对非确定性 hash() 的安全实现 (使用 hashlib)
    """

    def __init__(
        self, 
        capacity: int = 1000000, 
        error_rate: float = 0.001, 
        filepath: Optional[str] = None
    ) -> None:
        """
        Args:
            capacity: 预估处理的元素数量
            error_rate: 容许的假阳性概率
            filepath: 持久化文件路径
        """
        self.capacity = capacity
        self.error_rate = error_rate
        self.filepath = filepath
        
        # 计算位数组大小 m 和哈希函数数量 k
        # m = -(n * ln(p)) / (ln(2)^2)
        self.bit_size = int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.hash_count = int((self.bit_size / capacity) * math.log(2))
        
        # 使用 bytearray 存储 (8 bit per index)
        self.bit_array = bytearray(math.ceil(self.bit_size / 8))
        self.count = 0
        
        if filepath and os.path.exists(filepath):
            self.load()

    def _get_hashes(self, item: Any) -> List[int]:
        """使用 Double Hashing 模拟 k 个哈希函数"""
        item_str = str(item).encode('utf-8')
        
        # 使用 MD5 和 SHA1 模拟两个基础哈希函数
        h1 = int(hashlib.md5(item_str).hexdigest(), 16)
        h2 = int(hashlib.sha1(item_str).hexdigest(), 16)
        
        hashes = []
        for i in range(self.hash_count):
            # gi(x) = h1(x) + i * h2(x)
            pos = (h1 + i * h2) % self.bit_size
            hashes.append(pos)
        return hashes

    def add(self, item: Any) -> None:
        """添加元素"""
        for pos in self._get_hashes(item):
            byte_index = pos // 8
            bit_index = pos % 8
            self.bit_array[byte_index] |= (1 << bit_index)
        self.count += 1

    def __contains__(self, item: Any) -> bool:
        """检查元素是否存在"""
        for pos in self._get_hashes(item):
            byte_index = pos // 8
            bit_index = pos % 8
            if not (self.bit_array[byte_index] & (1 << bit_index)):
                return False
        return True

    def save(self) -> None:
        """持久化到磁盘"""
        if not self.filepath:
            return
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, 'wb') as f:
                data = {
                    'capacity': self.capacity,
                    'error_rate': self.error_rate,
                    'count': self.count,
                    'bit_array': self.bit_array
                }
                pickle.dump(data, f)
            logger.info(f"Bloom Filter saved to {self.filepath} (Count: {self.count})")
        except Exception as e:
            logger.error(f"Failed to save Bloom Filter: {e}")

    def load(self) -> None:
        """从磁盘加载"""
        if not self.filepath or not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, 'rb') as f:
                data = pickle.load(f)
                if data.get('capacity') == self.capacity and data.get('error_rate') == self.error_rate:
                    self.bit_array = data['bit_array']
                    self.count = data.get('count', 0)
                    logger.info(f"Bloom Filter loaded from {self.filepath}. Count: {self.count}")
                else:
                    logger.warning("Bloom Filter params changed, initialization required.")
        except Exception as e:
            logger.error(f"Failed to load Bloom Filter: {e}")

class BloomFilterManager:
    """管理多个布隆过滤器单例"""
    _filters: dict[str, BloomFilter] = {}

    @classmethod
    def get_filter(cls, name: str, **kwargs: Any) -> BloomFilter:
        if name not in cls._filters:
            cls._filters[name] = BloomFilter(**kwargs)
        return cls._filters[name]

    @classmethod
    def clear(cls) -> None:
        """清理所有过滤器 (Test only)"""
        cls._filters.clear()

# 向后兼容性别名
GlobalBloomFilter = BloomFilterManager
