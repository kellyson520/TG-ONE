"""
令牌桶限流器单元测试
"""
import pytest
import asyncio
import time
from utils.network.rate_limiter import TokenBucket, RateLimiterManager, RateLimitConfig


class TestTokenBucket:
    """测试令牌桶基本功能"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        config = RateLimitConfig(rate=10.0, capacity=20)
        tb = TokenBucket(config)
        assert tb.config.rate == 10.0
        assert tb.config.capacity == 20
        assert tb.tokens == 20.0
    
    @pytest.mark.asyncio
    async def test_consume_success(self):
        """测试成功消耗令牌"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        result = await tb.try_acquire(5.0)
        assert result is True
        assert tb.tokens == 5.0
    
    @pytest.mark.asyncio
    async def test_consume_failure(self):
        """测试令牌不足"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        # 消耗所有令牌
        await tb.try_acquire(10.0)
        
        # 再次消耗应该失败
        result = await tb.try_acquire(1.0)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_refill(self):
        """测试令牌补充"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        # 消耗所有令牌
        await tb.try_acquire(10.0)
        assert tb.tokens == 0.0
        
        # 等待足够时间补充
        await asyncio.sleep(1.2)
        
        result = await tb.try_acquire(5.0)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_capacity_limit(self):
        """测试容量上限"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        # 等待足够长时间
        await asyncio.sleep(1.5)
        
        # 令牌数不应超过容量
        assert tb.tokens <= 10.0
    
    @pytest.mark.asyncio
    async def test_wait_consume(self):
        """测试等待消耗 (Blocking)"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        # 消耗所有令牌
        await tb.try_acquire(10.0)
        
        # 等待消耗应该阻塞直到有足够令牌
        start = time.time()
        await tb.acquire(5.0)
        elapsed = time.time() - start
        
        # 应该等待约0.5秒
        assert 0.4 < elapsed < 0.8
    
    @pytest.mark.asyncio
    async def test_burst_support(self):
        """测试突发流量支持"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=30))
        
        # 应该能够处理突发的30个请求
        for _ in range(30):
            result = await tb.try_acquire(1.0)
            assert result is True
        
        # 第31个应该失败
        result = await tb.try_acquire(1.0)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_fractional_tokens(self):
        """测试小数令牌"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        result = await tb.try_acquire(0.5)
        assert result is True
        assert abs(tb.tokens - 9.5) < 0.01
    
    @pytest.mark.asyncio
    async def test_concurrent_consume(self):
        """测试并发消耗"""
        tb = TokenBucket(RateLimitConfig(rate=100.0, capacity=100))
        
        async def consumer():
            return await tb.try_acquire(1.0)
        
        # 并发100个消费者
        results = await asyncio.gather(*[consumer() for _ in range(100)])
        
        # 所有应该成功
        assert all(results)
        assert tb.tokens < 0.1
    

class TestRateLimiterManager:
    """测试限流器管理器"""
    
    @pytest.mark.asyncio
    async def test_get_limiter(self):
        """测试获取限流器"""
        limiter1 = RateLimiterManager.get_limiter("test1")
        limiter2 = RateLimiterManager.get_limiter("test1")
        limiter3 = RateLimiterManager.get_limiter("test2")
        
        assert limiter1 is limiter2
        assert limiter1 is not limiter3
    
    @pytest.mark.asyncio
    async def test_custom_parameters(self):
        """测试自定义参数"""
        config = RateLimitConfig(rate=5.0, capacity=15)
        limiter = RateLimiterManager.get_limiter("custom", config=config)
        
        assert limiter.config.rate == 5.0
        assert limiter.config.capacity == 15


class TestTokenBucketScenarios:
    """测试实际应用场景"""
    
    @pytest.mark.asyncio
    async def test_telegram_api_limit(self):
        """测试Telegram API限流场景"""
        tb = TokenBucket(RateLimitConfig(rate=30.0, capacity=30))
        
        messages_sent = 0
        start = time.time()
        
        # 尝试发送100条消息
        for _ in range(100):
            if await tb.try_acquire(1.0):
                messages_sent += 1
            else:
                await tb.acquire(1.0)
                messages_sent += 1
        
        elapsed = time.time() - start
        assert 2.0 < elapsed < 4.0
        assert messages_sent == 100
    
    @pytest.mark.asyncio
    async def test_smooth_rate_limiting(self):
        """测试平滑限流"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        
        # 先消耗完初始令牌
        while await tb.try_acquire(1.0):
            pass
            
        timestamps = []
        
        # 发送20条消息
        for _ in range(20):
            await tb.acquire(1.0)
            timestamps.append(time.time())
        
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        avg_interval = sum(intervals) / len(intervals)
        
        assert 0.08 < avg_interval < 0.15


class TestTokenBucketEdgeCases:
    """测试边界情况"""
    
    @pytest.mark.asyncio
    async def test_zero_rate(self):
        """测试零速率"""
        config = RateLimitConfig(rate=0.0, capacity=10)
        tb = TokenBucket(config)
        
        while await tb.try_acquire(1.0):
            pass
        
        await asyncio.sleep(0.5)
        result = await tb.try_acquire(1.0)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_very_high_rate(self):
        """测试极高速率"""
        tb = TokenBucket(RateLimitConfig(rate=1000.0, capacity=1000))
        
        start = time.time()
        for _ in range(1000):
            await tb.acquire(1.0)
        elapsed = time.time() - start
        assert elapsed < 1.5
    
    @pytest.mark.asyncio
    async def test_consume_more_than_capacity(self):
        """测试消耗超过容量"""
        tb = TokenBucket(RateLimitConfig(rate=10.0, capacity=10))
        result = await tb.try_acquire(20.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_negative_consume(self):
        pass

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
