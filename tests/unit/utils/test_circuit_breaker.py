import pytest
import asyncio
import time
from services.network.circuit_breaker import CircuitBreaker, CircuitOpenException, circuit_breaker

class MockService:
    def __init__(self):
        self.fail = False
    
    async def risky_operation(self):
        if self.fail:
            raise ValueError("Something went wrong")
        return "Success"

@pytest.mark.asyncio
async def test_circuit_breaker_normal_flow():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    service = MockService()
    
    # 1. 正常调用
    assert await cb.call(service.risky_operation) == "Success"
    assert cb.state.value == "CLOSED"

@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, expected_exceptions=(ValueError,))
    service = MockService()
    service.fail = True
    
    # Failure 1
    with pytest.raises(ValueError):
        await cb.call(service.risky_operation)
    assert cb.state.value == "CLOSED"
    
    # Failure 2 -> Opens
    with pytest.raises(ValueError):
        await cb.call(service.risky_operation)
    assert cb.state.value == "OPEN"
    
    # Fast Fail
    with pytest.raises(CircuitOpenException):
        await cb.call(service.risky_operation)

@pytest.mark.asyncio
async def test_circuit_breaker_recovery():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.2, expected_exceptions=(ValueError,))
    service = MockService()
    service.fail = True
    
    # Trigger Open
    with pytest.raises(ValueError):
        await cb.call(service.risky_operation)
    assert cb.state.value == "OPEN"
    
    # Wait for timeout
    await asyncio.sleep(0.3)
    
    # Service recovers
    service.fail = False
    
    # Next call should be HALF_OPEN -> Success -> CLOSED
    assert await cb.call(service.risky_operation) == "Success"
    assert cb.state.value == "CLOSED"

@pytest.mark.asyncio
async def test_circuit_breaker_relapse():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.2, expected_exceptions=(ValueError,))
    service = MockService()
    service.fail = True
    
    # Trigger Open
    with pytest.raises(ValueError):
        await cb.call(service.risky_operation)
    
    # Wait for recovery
    await asyncio.sleep(0.3)
    
    # Service still failing
    # HALF_OPEN -> Failure -> OPEN
    with pytest.raises(ValueError):
        await cb.call(service.risky_operation)
    
    assert cb.state.value == "OPEN"
    
    # Should be locked again
    with pytest.raises(CircuitOpenException):
        await cb.call(service.risky_operation)

@pytest.mark.asyncio
async def test_decorator_usage():
    service = MockService()
    
    @circuit_breaker(threshold=2, timeout=0.1, exc=(ValueError,))
    async def decorated_func():
        return await service.risky_operation()
        
    # Success
    assert await decorated_func() == "Success"
    
    # Failures
    service.fail = True
    with pytest.raises(ValueError):
        await decorated_func()
        
    with pytest.raises(ValueError):
        await decorated_func()
        
    # Open
    with pytest.raises(CircuitOpenException):
        await decorated_func()
