from core.algorithms.bloom_filter import BloomFilter
import logging
import os

logger = logging.getLogger(__name__)

# [Consolidation] 现在直接基于 core.algorithms.bloom_filter
# 保持单例导出以简化旧代码集成

from core.config import settings

# 配置默认存放路径
BLOOM_DATA_PATH = settings.DATA_ROOT / "dedup_bloom.dat"

# 确保目录存在
os.makedirs(settings.DATA_ROOT, exist_ok=True)

# 全局单例
bloom_filter_service = BloomFilter(
    capacity=1000000, 
    error_rate=0.001, 
    filepath=BLOOM_DATA_PATH
)

logger.info("Bloom Filter Service initialized using consolidated utils implementation")
