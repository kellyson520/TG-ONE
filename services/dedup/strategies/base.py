from abc import ABC, abstractmethod
from typing import Optional
from services.dedup.types import DedupContext, DedupResult

class BaseDedupStrategy(ABC):
    """去重策略基类"""
    
    @abstractmethod
    async def process(self, ctx: DedupContext) -> Optional[DedupResult]:
        """
        执行策略检查
        如果命中去重(is_duplicate=True)，则返回 Result。
        如果不命中，返回 None 或 Result(is_duplicate=False)
        """
        pass
    
    @abstractmethod
    async def record(self, ctx: DedupContext, result: DedupResult):
        """记录状态 (供后续去重)"""
        pass
