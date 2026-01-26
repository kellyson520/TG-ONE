"""
Standardized Rate Limiter (Adaptive Leaky Bucket)
整合了之前的简单 TokenBucket 与 复杂的 Adaptive Leaky Bucket。
"""
import asyncio
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class Priority(Enum):
    """操作优先级"""
    HIGH = 1
    NORMAL = 2
    LOW = 3

@dataclass
class RateLimitConfig:
    """限流配置"""
    rate: float            # 每秒允许的操作数
    capacity: int          # 桶容量 (允许的突发数)
    adaptive: bool = False # 是否启用自适应调整
    min_rate: float = 1.0  # 最小速率
    max_rate: float = 1000.0  # 最大速率

class LeakyBucket:
    """
    自适应漏桶限流器 (Adaptive Leaky Bucket)
    """
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = float(config.capacity)
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "accepted_requests": 0,
            "rejected_requests": 0,
            "total_wait_time": 0.0,
            "current_rate": config.rate
        }
        
        # 自适应调整
        self._load_history = []
        self._last_adjustment = time.time()
        self._adjustment_interval = 10.0

    async def acquire(self, tokens: float = 1.0, timeout: Optional[float] = None) -> bool:
        """
        线程/协程安全获取令牌 (阻塞模式)
        """
        start_time = time.time()
        while True:
            async with self._lock:
                self._refill()
                self._stats["total_requests"] += 1
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self._stats["accepted_requests"] += 1
                    self._stats["total_wait_time"] += (time.time() - start_time)
                    return True
                
                needed = tokens - self.tokens
                wait_time = needed / self.config.rate
            
            # 检查超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    async with self._lock:
                        self._stats["rejected_requests"] += 1
                    return False
                wait_time = min(wait_time, timeout - elapsed)
            
            await asyncio.sleep(wait_time)

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """非阻塞模式"""
        async with self._lock:
            self._refill()
            self._stats["total_requests"] += 1
            if self.tokens >= tokens:
                self.tokens -= tokens
                self._stats["accepted_requests"] += 1
                return True
            self._stats["rejected_requests"] += 1
            return False

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_update
        refill_amount = elapsed * self.config.rate
        self.tokens = min(self.config.capacity, self.tokens + refill_amount)
        self.last_update = now
        
        if self.config.adaptive:
            self._adaptive_adjust()

    def _adaptive_adjust(self):
        now = time.time()
        if now - self._last_adjustment < self._adjustment_interval:
            return
        
        self._last_adjustment = now
        total = self._stats["total_requests"]
        if total > 0:
            load_rate = self._stats["rejected_requests"] / total
            self._load_history.append(load_rate)
            if len(self._load_history) > 10: self._load_history.pop(0)
            
            avg_load = sum(self._load_history) / len(self._load_history)
            
            # 简单 AIMD 策略
            if avg_load > 0.5:
                self.config.rate = max(self.config.min_rate, self.config.rate * 0.8)
            elif avg_load < 0.1:
                self.config.rate = min(self.config.max_rate, self.config.rate * 1.1)
            
            self._stats["current_rate"] = self.config.rate

    def get_stats(self) -> Dict[str, Any]:
        with_current = self._stats.copy()
        with_current["tokens_available"] = self.tokens
        return with_current

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_requests": 0,
            "accepted_requests": 0,
            "rejected_requests": 0,
            "total_wait_time": 0.0,
            "current_rate": self.config.rate
        }
        self._load_history = []

class RateLimiterPool:
    """限流器池管理"""
    _limiters: Dict[str, LeakyBucket] = {}
    
    PRESETS = {
        "db_writes": RateLimitConfig(rate=100.0, capacity=200, adaptive=True),
        "api_calls": RateLimitConfig(rate=20.0, capacity=30, adaptive=True),
        "file_io": RateLimitConfig(rate=50.0, capacity=100, adaptive=False),
    }
    
    @classmethod
    def get_limiter(cls, name: str, config: Optional[RateLimitConfig] = None) -> LeakyBucket:
        if name not in cls._limiters:
            if config is None:
                config = cls.PRESETS.get(name, RateLimitConfig(rate=30.0, capacity=50))
            cls._limiters[name] = LeakyBucket(config)
        return cls._limiters[name]

# Backward Compatibility (Wait, previous utils version was TokenBucket)
TokenBucket = LeakyBucket
RateLimiterManager = RateLimiterPool
