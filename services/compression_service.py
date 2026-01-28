"""
LZ4 Compression Service
提供透明的数据压缩/解压缩功能，优化数据库存储
"""
import logging
from typing import Union
import zlib  # Fallback compression

logger = logging.getLogger(__name__)

# Try to import lz4, fallback to zlib if unavailable
try:
    import lz4.frame
    HAS_LZ4 = True
    logger.info("LZ4 compression available")
except ImportError:
    HAS_LZ4 = False
    logger.warning("LZ4 not available, using zlib fallback")


class CompressionService:
    """
    数据压缩服务
    
    特性:
    - 优先使用 LZ4 (高速压缩)
    - 自动降级到 zlib (标准库)
    - 智能阈值判断 (小数据不压缩)
    - 透明编解码
    """
    
    # 压缩阈值 (字节)
    DEFAULT_THRESHOLD = 1024  # 1KB
    
    def __init__(self, threshold: int = DEFAULT_THRESHOLD, use_lz4: bool = True):
        """
        Args:
            threshold: 压缩阈值，小于此值的数据不压缩
            use_lz4: 是否优先使用 LZ4 (如果可用)
        """
        self.threshold = threshold
        self.use_lz4 = use_lz4 and HAS_LZ4
        self._stats = {
            "compressed_count": 0,
            "decompressed_count": 0,
            "total_original_bytes": 0,
            "total_compressed_bytes": 0,
            "compression_errors": 0
        }
    
    def should_compress(self, data: Union[str, bytes]) -> bool:
        """判断是否应该压缩数据"""
        if isinstance(data, str):
            size = len(data.encode('utf-8'))
        else:
            size = len(data)
        return size >= self.threshold
    
    def compress(self, data: str) -> bytes:
        """
        压缩字符串数据
        
        Args:
            data: 待压缩的字符串
            
        Returns:
            压缩后的字节数据
        """
        if not data:
            return b''
        
        try:
            data_bytes = data.encode('utf-8')
            original_size = len(data_bytes)
            
            # 小数据不压缩
            if not self.should_compress(data):
                logger.debug(f"Data too small ({original_size} bytes), skipping compression")
                return data_bytes
            
            # 压缩
            if self.use_lz4:
                compressed = lz4.frame.compress(data_bytes)
            else:
                compressed = zlib.compress(data_bytes, level=6)  # 平衡速度和压缩率
            
            compressed_size = len(compressed)
            
            # 更新统计
            self._stats["compressed_count"] += 1
            self._stats["total_original_bytes"] += original_size
            self._stats["total_compressed_bytes"] += compressed_size
            
            ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            logger.debug(f"Compressed {original_size} -> {compressed_size} bytes (ratio: {ratio:.2f}x)")
            
            return compressed
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            self._stats["compression_errors"] += 1
            # 压缩失败，返回原始数据
            return data.encode('utf-8')
    
    def decompress(self, data: bytes) -> str:
        """
        解压缩字节数据
        
        Args:
            data: 压缩的字节数据
            
        Returns:
            解压后的字符串
        """
        if not data:
            return ''
        
        try:
            # 尝试解压
            if self.use_lz4:
                try:
                    decompressed = lz4.frame.decompress(data)
                except Exception:
                    # LZ4 解压失败，可能是 zlib 压缩的或未压缩
                    try:
                        decompressed = zlib.decompress(data)
                    except Exception:
                        # 可能是未压缩的数据
                        decompressed = data
            else:
                try:
                    decompressed = zlib.decompress(data)
                except Exception:
                    # 可能是未压缩的数据
                    decompressed = data
            
            self._stats["decompressed_count"] += 1
            return decompressed.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            self._stats["compression_errors"] += 1
            # 解压失败，尝试直接解码
            try:
                return data.decode('utf-8')
            except Exception:
                return ''
    
    def compress_if_needed(self, data: str) -> tuple[bytes, bool]:
        """
        智能压缩：只在必要时压缩
        
        Returns:
            (compressed_data, is_compressed)
        """
        if self.should_compress(data):
            return self.compress(data), True
        else:
            return data.encode('utf-8'), False
    
    def get_stats(self) -> dict:
        """获取压缩统计信息"""
        stats = self._stats.copy()
        
        if stats["total_original_bytes"] > 0:
            stats["avg_compression_ratio"] = (
                stats["total_original_bytes"] / stats["total_compressed_bytes"]
                if stats["total_compressed_bytes"] > 0 else 1.0
            )
            stats["space_saved_bytes"] = stats["total_original_bytes"] - stats["total_compressed_bytes"]
            stats["space_saved_percent"] = (
                (stats["space_saved_bytes"] / stats["total_original_bytes"]) * 100
            )
        else:
            stats["avg_compression_ratio"] = 1.0
            stats["space_saved_bytes"] = 0
            stats["space_saved_percent"] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "compressed_count": 0,
            "decompressed_count": 0,
            "total_original_bytes": 0,
            "total_compressed_bytes": 0,
            "compression_errors": 0
        }


# 全局单例
compression_service = CompressionService()
