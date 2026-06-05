from core.algorithms.bloom_filter import BloomFilter
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# [Consolidation] 现在直接基于 core.algorithms.bloom_filter
# 保持单例导出以简化旧代码集成

class LazyBloomFilterService:
    """Import-safe proxy for the global dedup Bloom filter."""

    def __init__(self) -> None:
        self._instance: Optional[BloomFilter] = None

    def _get(self) -> BloomFilter:
        if self._instance is None:
            from core.config import settings

            data_path = settings.DATA_ROOT / "dedup_bloom.dat"
            os.makedirs(settings.DATA_ROOT, exist_ok=True)
            self._instance = BloomFilter(
                capacity=1000000,
                error_rate=0.001,
                filepath=data_path
            )
            logger.info("Bloom Filter Service initialized using consolidated utils implementation")
        return self._instance

    def add(self, item) -> None:
        self._get().add(item)

    def save(self) -> bool:
        if self._instance is None:
            return False
        self._instance.save()
        return True

    def __contains__(self, item) -> bool:
        return item in self._get()

    def __getattr__(self, name):
        return getattr(self._get(), name)


# 全局懒加载单例
bloom_filter_service = LazyBloomFilterService()
