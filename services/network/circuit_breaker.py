import time
import asyncio
from enum import Enum
from typing import Callable, Any
from functools import wraps

class CircuitState(Enum):
    CLOSED = "CLOSED"       # 正常状态
    OPEN = "OPEN"           # 熔断开启（拒绝请求）
    HALF_OPEN = "HALF_OPEN" # 半开（尝试恢复）

class CircuitOpenException(Exception):
    """当熔断器处于 OPEN 状态时抛出"""
    pass

class CircuitBreaker:
    """
    有限状态机熔断器实现 (Finite State Machine Circuit Breaker)
    
    States:
        CLOSED -> Failures > threshold -> OPEN
        OPEN -> timeout expired -> HALF_OPEN
        HALF_OPEN -> Success -> CLOSED
        HALF_OPEN -> Failure -> OPEN
    """
    
    def __init__(
        self, 
        name: str = "default",
        failure_threshold: int = 5, 
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple = (Exception,)
    ):
        """
        Args:
            name: 熔断器名称
            failure_threshold: 连续失败多少次触发熔断
            recovery_timeout: 熔断后等待多少秒进入半开状态
            expected_exceptions: 哪些异常算作"失败"
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行受保护的函数调用
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                # 检查是否冷却完毕，可以进入半开
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    raise CircuitOpenException(f"Circuit {self.name} is OPEN")
            
            # HALF_OPEN 状态只允许一个请求通过（由于锁的存在，天然串行）
            # 如果是 HALF_OPEN，我们尝试执行。成功则关闭，失败则重新打开。

        try:
            result = await func(*args, **kwargs)
            
            # 成功执行后的状态变更
            if self.state != CircuitState.CLOSED:
                await self._on_success()
            else:
                # 即使是 CLOSED，也要重置失败计数（可选，取决于是否滑动窗口。这里是连续失败计数）
                # 简单实现：成功一次即重置连续失败计数
                if self.failure_count > 0:
                    async with self._lock:
                        self.failure_count = 0
            
            return result
            
        except self.expected_exceptions as e:
            # 捕获已知异常，记录失败
            await self._on_failure()
            raise e

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.CLOSED)
                self.failure_count = 0
            elif self.state == CircuitState.OPEN:
                # 理论上不应到达这里，除非并发边界情况
                pass

    async def _on_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        # 实际项目中这里可以加日志
        # print(f"Circuit {self.name} changed state: {self.state} -> {new_state}")
        self.state = new_state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

def circuit_breaker(
    name: str = None, 
    threshold: int = 5, 
    timeout: float = 30.0,
    exc: tuple = (Exception,)
):
    """
    装饰器用法
    """
    def decorator(func):
        # 为每个函数实例创建一个熔断器? 
        # 注意：如果是方法，这意味着每个实例都有自己的熔断器。
        # 这里简化处理，不共享熔断器状态。
        breaker = CircuitBreaker(
            name=name or func.__name__,
            failure_threshold=threshold,
            recovery_timeout=timeout,
            expected_exceptions=exc
        )
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
