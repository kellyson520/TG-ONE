from typing import Optional
from services.network.rate_limiter import RateLimiterPool
import logging

logger = logging.getLogger(__name__)

# [Consolidation] 现在基于 services.network.rate_limiter
# 保持 RateLimiterPool 的直接暴露以兼容旧代码

# 额外添加 services 层的特有配置或初始化逻辑（如有）

async def rate_limit(name: str, tokens: float = 1.0, timeout: Optional[float] = None) -> bool:
    limiter = RateLimiterPool.get_limiter(name)
    return await limiter.acquire(tokens, timeout)
