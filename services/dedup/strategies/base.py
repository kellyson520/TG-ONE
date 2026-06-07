from abc import ABC, abstractmethod
from typing import Optional
from services.dedup.types import DedupContext, DedupResult


class BaseDedupStrategy(ABC):
    """去重策略基类"""

    async def _get_pcache_best_effort(
        self,
        ctx: DedupContext,
        key: str,
        default=None,
    ):
        """Best-effort PCache lookup.

        Cache failures degrade to miss.
        """
        try:
            return await ctx.pcache_repo.get(key)
        except Exception as exc:
            ctx.logger.debug("PCache读取失败 (%s): %s", key, exc)
            return default

    async def _set_pcache_best_effort(
        self,
        ctx: DedupContext,
        key: str,
        value: str = "1",
        expire: int = 86400,
    ) -> None:
        """Best-effort PCache backfill.

        Cache failures must not affect dedup.
        """
        try:
            await ctx.pcache_repo.set(key, value, expire=expire)
        except Exception as exc:
            ctx.logger.debug("PCache回填失败 (%s): %s", key, exc)

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
