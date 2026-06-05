"""
Performance Test: Bloom Filter Efficiency
测试布隆过滤器的查询性能与准确性
"""
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.bloom_filter import BloomFilter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_bloom_filter_performance():
    """测试布隆过滤器性能"""
    
    # Create bloom filter
    bf = BloomFilter(capacity=100000, error_rate=0.001, filepath=":memory:")
    
    logger.info("=" * 60)
    logger.info("Performance Test: Bloom Filter")
    logger.info("=" * 60)
    
    # Test 1: Add performance
    test_count = 50000
    logger.info(f"\nTest 1: Adding {test_count} items")
    
    start = time.time()
    for i in range(test_count):
        bf.add(f"signature_{i}")
    add_time = time.time() - start
    
    logger.info(f"Add Time: {add_time:.3f}s ({test_count/add_time:.0f} ops/s)")
    
    # Test 2: Positive lookup (items that exist)
    logger.info(f"\nTest 2: Positive Lookup ({test_count} existing items)")
    
    start = time.time()
    hits = 0
    for i in range(test_count):
        if f"signature_{i}" in bf:
            hits += 1
    lookup_time = time.time() - start
    
    logger.info(f"Lookup Time: {lookup_time:.3f}s ({test_count/lookup_time:.0f} ops/s)")
    logger.info(f"Hit Rate: {hits}/{test_count} ({hits/test_count*100:.1f}%)")
    
    # Test 3: Negative lookup (items that don't exist)
    logger.info(f"\nTest 3: Negative Lookup ({test_count} non-existing items)")
    
    start = time.time()
    false_positives = 0
    for i in range(test_count, test_count * 2):
        if f"signature_{i}" in bf:
            false_positives += 1
    negative_lookup_time = time.time() - start
    
    logger.info(f"Lookup Time: {negative_lookup_time:.3f}s ({test_count/negative_lookup_time:.0f} ops/s)")
    logger.info(f"False Positive Rate: {false_positives}/{test_count} ({false_positives/test_count*100:.3f}%)")
    logger.info(f"Expected FP Rate: {bf.error_rate*100:.3f}%")
    
    # Test 4: Memory usage
    import sys
    memory_bytes = sys.getsizeof(bf.bit_array)
    logger.info(f"\nMemory Usage: {memory_bytes / 1024:.2f} KB")
    logger.info(f"Bits per item: {bf.bit_size / test_count:.2f}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    logger.info(f"Total Items: {test_count}")
    logger.info(f"Add Speed: {test_count/add_time:.0f} ops/s")
    logger.info(f"Lookup Speed: {test_count/lookup_time:.0f} ops/s")
    logger.info(f"False Positive Rate: {false_positives/test_count*100:.3f}% (Target: {bf.error_rate*100:.3f}%)")
    logger.info(f"Memory Efficiency: {memory_bytes/test_count:.2f} bytes/item")

if __name__ == "__main__":
    test_bloom_filter_performance()
