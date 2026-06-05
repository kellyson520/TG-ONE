"""
Performance Test: Rate Limiter
测试限流器的性能和准确性
"""
import asyncio
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.rate_limiter import LeakyBucket, RateLimitConfig, RateLimiterPool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_rate_limiting():
    """测试基本限流功能"""
    logger.info("=" * 60)
    logger.info("Test 1: Basic Rate Limiting")
    logger.info("=" * 60)
    
    # 创建限流器: 10 ops/s, capacity 20
    config = RateLimitConfig(rate=10.0, capacity=20, adaptive=False)
    limiter = LeakyBucket(config)
    
    # Test 1: Burst handling
    logger.info("\nTest 1.1: Burst Handling (20 requests immediately)")
    start = time.time()
    success_count = 0
    
    for i in range(20):
        if await limiter.try_acquire():
            success_count += 1
    
    elapsed = time.time() - start
    logger.info(f"Accepted: {success_count}/20 in {elapsed:.3f}s")
    logger.info(f"Expected: 20 (within capacity)")
    
    # Test 2: Rate limiting
    logger.info("\nTest 1.2: Rate Limiting (10 more requests)")
    success_count = 0
    for i in range(10):
        if await limiter.try_acquire():
            success_count += 1
    
    logger.info(f"Accepted: {success_count}/10")
    logger.info(f"Expected: 0 (bucket empty)")
    
    # Test 3: Refill
    logger.info("\nTest 1.3: Refill (wait 1 second)")
    await asyncio.sleep(1.0)
    
    success_count = 0
    for i in range(15):
        if await limiter.try_acquire():
            success_count += 1
    
    logger.info(f"Accepted: {success_count}/15")
    logger.info(f"Expected: ~10 (refilled at 10 ops/s)")

async def test_blocking_mode():
    """测试阻塞模式"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Blocking Mode")
    logger.info("=" * 60)
    
    config = RateLimitConfig(rate=50.0, capacity=10, adaptive=False)
    limiter = LeakyBucket(config)
    
    # Exhaust capacity
    for i in range(10):
        await limiter.try_acquire()
    
    logger.info("\nTest 2.1: Blocking Acquire (should wait)")
    start = time.time()
    result = await limiter.acquire(tokens=5.0, timeout=1.0)
    elapsed = time.time() - start
    
    logger.info(f"Result: {result}")
    logger.info(f"Wait Time: {elapsed:.3f}s")
    logger.info(f"Expected: ~0.1s (5 tokens / 50 rate)")

async def test_adaptive_adjustment():
    """测试自适应调整"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 3: Adaptive Rate Adjustment")
    logger.info("=" * 60)
    
    config = RateLimitConfig(rate=20.0, capacity=30, adaptive=True, min_rate=5.0, max_rate=100.0)
    limiter = LeakyBucket(config)
    
    logger.info(f"\nInitial Rate: {limiter.config.rate} ops/s")
    
    # Simulate high load (many rejections)
    logger.info("\nSimulating high load (100 requests)...")
    for i in range(100):
        await limiter.try_acquire()
        if i % 10 == 0:
            await asyncio.sleep(0.01)  # Small delay
    
    stats = limiter.get_stats()
    logger.info(f"Rejection Rate: {stats['rejection_rate']:.2%}")
    logger.info(f"Adjusted Rate: {limiter.config.rate} ops/s")
    
    # Wait for adjustment
    await asyncio.sleep(11)  # Adjustment interval is 10s
    
    # Simulate low load
    logger.info("\nSimulating low load (wait and retry)...")
    await asyncio.sleep(2)
    for i in range(20):
        await limiter.try_acquire()
        await asyncio.sleep(0.1)
    
    await asyncio.sleep(11)
    stats = limiter.get_stats()
    logger.info(f"Rejection Rate: {stats['rejection_rate']:.2%}")
    logger.info(f"Adjusted Rate: {limiter.config.rate} ops/s")

async def test_rate_limiter_pool():
    """测试限流器池"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Rate Limiter Pool")
    logger.info("=" * 60)
    
    # Get limiters from pool
    db_limiter = RateLimiterPool.get_limiter("db_writes")
    api_limiter = RateLimiterPool.get_limiter("api_calls")
    
    logger.info(f"\nDB Writes Limiter: {db_limiter.config.rate} ops/s")
    logger.info(f"API Calls Limiter: {api_limiter.config.rate} ops/s")
    
    # Simulate operations
    for i in range(50):
        await db_limiter.try_acquire()
    
    for i in range(20):
        await api_limiter.try_acquire()
    
    # Get all stats
    all_stats = RateLimiterPool.get_all_stats()
    
    logger.info("\nPool Statistics:")
    for name, stats in all_stats.items():
        logger.info(f"\n{name}:")
        logger.info(f"  Total Requests: {stats['total_requests']}")
        logger.info(f"  Accepted: {stats['accepted_requests']}")
        logger.info(f"  Rejected: {stats['rejected_requests']}")
        logger.info(f"  Acceptance Rate: {stats['acceptance_rate']:.2%}")

async def main():
    logger.info("=" * 60)
    logger.info("Performance Test: Rate Limiter")
    logger.info("=" * 60)
    
    await test_basic_rate_limiting()
    await test_blocking_mode()
    await test_adaptive_adjustment()
    await test_rate_limiter_pool()
    
    logger.info("\n" + "=" * 60)
    logger.info("All Tests Completed")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
