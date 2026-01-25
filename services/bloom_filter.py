from utils.processing.bloom_filter import BloomFilter
import logging
import os

logger = logging.getLogger(__name__)

# [Consolidation] 现在直接基于 utils.processing.bloom_filter
# 保持单例导出以简化旧代码集成

# 配置默认存放路径
DATA_DIR = "data"
BLOOM_DATA_PATH = os.path.join(DATA_DIR, "dedup_bloom.dat")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# 全局单例
bloom_filter_service = BloomFilter(
    capacity=1000000, 
    error_rate=0.001, 
    filepath=BLOOM_DATA_PATH
)

logger.info("Bloom Filter Service initialized using consolidated utils implementation")
