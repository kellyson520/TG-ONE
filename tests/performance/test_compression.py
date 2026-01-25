"""
Performance Test: Compression Service
测试压缩服务的性能和压缩率
"""
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.compression_service import CompressionService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_test_data(size_kb: int) -> str:
    """生成测试数据"""
    # 模拟 RSS 描述或日志内容
    base_text = """
    这是一条测试消息，包含中文和English混合内容。
    System log entry: Processing message ID 12345
    Timestamp: 2026-01-15 11:30:00
    Status: Success
    Details: Message forwarded successfully to target chat.
    """
    
    # 重复到指定大小
    target_bytes = size_kb * 1024
    repetitions = target_bytes // len(base_text.encode('utf-8')) + 1
    return (base_text * repetitions)[:target_bytes]

def test_compression_performance():
    """测试压缩性能"""
    
    logger.info("=" * 60)
    logger.info("Performance Test: Compression Service")
    logger.info("=" * 60)
    
    # 测试不同大小的数据
    test_sizes = [1, 5, 10, 50, 100]  # KB
    
    # 使用 LZ4 (如果可用)
    service_lz4 = CompressionService(use_lz4=True)
    # 使用 zlib
    service_zlib = CompressionService(use_lz4=False)
    
    for size_kb in test_sizes:
        logger.info(f"\n{'='*60}")
        logger.info(f"Test: {size_kb}KB Data")
        logger.info(f"{'='*60}")
        
        test_data = generate_test_data(size_kb)
        original_size = len(test_data.encode('utf-8'))
        
        # Test LZ4
        start = time.time()
        compressed_lz4 = service_lz4.compress(test_data)
        compress_time_lz4 = (time.time() - start) * 1000
        
        start = time.time()
        decompressed_lz4 = service_lz4.decompress(compressed_lz4)
        decompress_time_lz4 = (time.time() - start) * 1000
        
        compressed_size_lz4 = len(compressed_lz4)
        ratio_lz4 = original_size / compressed_size_lz4 if compressed_size_lz4 > 0 else 1.0
        
        # Test zlib
        start = time.time()
        compressed_zlib = service_zlib.compress(test_data)
        compress_time_zlib = (time.time() - start) * 1000
        
        start = time.time()
        decompressed_zlib = service_zlib.decompress(compressed_zlib)
        decompress_time_zlib = (time.time() - start) * 1000
        
        compressed_size_zlib = len(compressed_zlib)
        ratio_zlib = original_size / compressed_size_zlib if compressed_size_zlib > 0 else 1.0
        
        # Verify correctness
        assert decompressed_lz4 == test_data, "LZ4 decompression mismatch"
        assert decompressed_zlib == test_data, "zlib decompression mismatch"
        
        logger.info(f"Original Size: {original_size:,} bytes ({size_kb}KB)")
        logger.info(f"\nLZ4 Compression:")
        logger.info(f"  Compressed Size: {compressed_size_lz4:,} bytes")
        logger.info(f"  Compression Ratio: {ratio_lz4:.2f}x")
        logger.info(f"  Compress Time: {compress_time_lz4:.2f}ms")
        logger.info(f"  Decompress Time: {decompress_time_lz4:.2f}ms")
        logger.info(f"  Throughput: {original_size / (compress_time_lz4 / 1000) / 1024 / 1024:.2f} MB/s")
        
        logger.info(f"\nzlib Compression:")
        logger.info(f"  Compressed Size: {compressed_size_zlib:,} bytes")
        logger.info(f"  Compression Ratio: {ratio_zlib:.2f}x")
        logger.info(f"  Compress Time: {compress_time_zlib:.2f}ms")
        logger.info(f"  Decompress Time: {decompress_time_zlib:.2f}ms")
        logger.info(f"  Throughput: {original_size / (compress_time_zlib / 1000) / 1024 / 1024:.2f} MB/s")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Summary")
    logger.info(f"{'='*60}")
    
    stats_lz4 = service_lz4.get_stats()
    stats_zlib = service_zlib.get_stats()
    
    logger.info(f"\nLZ4 Stats:")
    logger.info(f"  Compressed Count: {stats_lz4['compressed_count']}")
    logger.info(f"  Avg Compression Ratio: {stats_lz4['avg_compression_ratio']:.2f}x")
    logger.info(f"  Space Saved: {stats_lz4['space_saved_bytes']:,} bytes ({stats_lz4['space_saved_percent']:.1f}%)")
    
    logger.info(f"\nzlib Stats:")
    logger.info(f"  Compressed Count: {stats_zlib['compressed_count']}")
    logger.info(f"  Avg Compression Ratio: {stats_zlib['avg_compression_ratio']:.2f}x")
    logger.info(f"  Space Saved: {stats_zlib['space_saved_bytes']:,} bytes ({stats_zlib['space_saved_percent']:.1f}%)")

if __name__ == "__main__":
    test_compression_performance()
