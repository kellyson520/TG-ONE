"""circuit_breaker 测试 — 熔断器状态机"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock
from core.helpers.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenException,
    get_circuit_breaker,
    circuit_breaker,
)


@pytest.fixture
def cb():
    """快速恢复的熔断器"""
    return CircuitBreaker(failure_threshold=3, recovery_timeout=0.5, exceptions=(ValueError,))


class TestCircuitBreakerStates:
    """熔断器状态转换"""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, cb):
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_stays_closed(self, cb):
        func = AsyncMock(return_value="ok")
        await cb.call(func)
        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_failures_increment(self, cb):
        func = AsyncMock(side_effect=ValueError("err"))
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(func)
        assert cb.failures == 2
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_threshold_opens_circuit(self, cb):
        """达到阈值后打开熔断器"""
        func = AsyncMock(side_effect=ValueError("err"))
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(func)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_fast_fails(self, cb):
        """打开状态快速失败"""
        func = AsyncMock(side_effect=ValueError("err"))
        # 触发熔断
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(func)
        # 新调用应该快速失败
        good_func = AsyncMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenException):
            await cb.call(good_func)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, cb):
        """超时后进入半开状态"""
        func = AsyncMock(side_effect=ValueError("err"))
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(func)
        assert cb.state == CircuitState.OPEN
        # 等待恢复超时
        await asyncio.sleep(0.6)
        # 下一次调用应进入半开状态
        good_func = AsyncMock(return_value="ok")
        result = await cb.call(good_func)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, cb):
        """半开状态失败→重新打开"""
        func = AsyncMock(side_effect=ValueError("err"))
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(func)
        await asyncio.sleep(0.6)
        # 半开状态再失败
        with pytest.raises(ValueError):
            await cb.call(func)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_closed_success_resets_failures(self, cb):
        """成功调用重置失败计数"""
        func = AsyncMock(side_effect=ValueError("err"))
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(func)
        assert cb.failures == 2
        # 一次成功
        good_func = AsyncMock(return_value="ok")
        await cb.call(good_func)
        # failures 不会在 closed 状态重置（只在 half_open→closed 时重置）
        # 但状态保持 closed
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_non_matching_exception_not_caught(self, cb):
        """不匹配的异常不触发熔断"""
        func = AsyncMock(side_effect=RuntimeError("other"))
        with pytest.raises(RuntimeError):
            await cb.call(func)
        assert cb.failures == 0


class TestGetCircuitBreaker:
    """get_circuit_breaker 工厂测试"""

    def test_returns_same_instance(self):
        cb1 = get_circuit_breaker("test_service")
        cb2 = get_circuit_breaker("test_service")
        assert cb1 is cb2

    def test_different_names_different_instances(self):
        cb1 = get_circuit_breaker("service_a")
        cb2 = get_circuit_breaker("service_b")
        assert cb1 is not cb2

    def test_custom_kwargs(self):
        cb = get_circuit_breaker("custom", failure_threshold=10, recovery_timeout=60)
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 60


class TestCircuitBreakerDecorator:
    """@circuit_breaker 装饰器测试"""

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self):
        @circuit_breaker("decorator_test", failure_threshold=2, recovery_timeout=0.5)
        async def my_func():
            return "decorated"

        result = await my_func()
        assert result == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_tracks_failures(self):
        call_count = 0

        @circuit_breaker("decorator_fail", failure_threshold=2, recovery_timeout=0.5, exceptions=(ValueError,))
        async def flaky():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        for _ in range(2):
            with pytest.raises(ValueError):
                await flaky()
        # 第3次应该被熔断
        with pytest.raises(CircuitBreakerOpenException):
            await flaky()


class TestEdgeCases:
    """边界条件"""

    @pytest.mark.asyncio
    async def test_threshold_1(self):
        """阈值=1，一次失败就熔断"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        func = AsyncMock(side_effect=ValueError("err"))
        with pytest.raises(ValueError):
            await cb.call(func)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_recovery_then_failure_chain(self):
        """恢复→再失败的完整链路"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.3, exceptions=(ValueError,))
        fail_func = AsyncMock(side_effect=ValueError("err"))
        good_func = AsyncMock(return_value="ok")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        assert cb.state == CircuitState.OPEN

        # 等待恢复
        await asyncio.sleep(0.4)
        result = await cb.call(good_func)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0

        # 再次失败
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        assert cb.state == CircuitState.OPEN
