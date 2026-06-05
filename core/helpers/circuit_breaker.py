import time
import asyncio
from typing import Callable, Any
import logging
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, fast fail
    HALF_OPEN = "half_open" # Testing if service is back

class CircuitBreaker:
    """
    通用熔断器实现 (Circuit Breaker Pattern)
    保护上游服务免受级联故障影响
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0, exceptions: tuple = (Exception,)):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.exceptions = exceptions
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0
        self.lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute the function with circuit breaker protection.
        """
        async with self.lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    logger.info(f"CircuitBreaker: Transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenException("Circuit is OPEN")

        try:
            result = await func(*args, **kwargs)
            
            if self.state == CircuitState.HALF_OPEN:
                async with self.lock:
                    self.state = CircuitState.CLOSED
                    self.failures = 0
                    logger.info(f"CircuitBreaker: Recovery successful, transitioning to CLOSED")
                    
            return result
        except self.exceptions as e:
            async with self.lock:
                self.failures += 1
                self.last_failure_time = time.time()
                
                if self.state == CircuitState.HALF_OPEN:
                     self.state = CircuitState.OPEN
                     logger.warning(f"CircuitBreaker: Recovery failed, transitioning back to OPEN")
                elif self.failures >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.error(f"CircuitBreaker: Failure threshold reached ({self.failures}), transitioning to OPEN")
            
            raise e

class CircuitBreakerOpenException(Exception):
    pass

# Global Map for Circuit Breakers per domain/service
_breakers = {}

def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(**kwargs)
    return _breakers[name]

def circuit_breaker(name: str, **cb_kwargs):
    """
    Decorator for async functions
    """
    def decorator(func):
        cb = get_circuit_breaker(name, **cb_kwargs)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)
        return wrapper
    return decorator
