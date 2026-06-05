"""
Unit Tests: Compression Service
"""
import pytest
from services.compression_service import CompressionService


class TestCompressionService:
    """测试压缩服务"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.service = CompressionService(threshold=100)
    
    def test_should_compress_small_data(self):
        """测试小数据不压缩"""
        small_text = "Hello World"
        assert not self.service.should_compress(small_text)
    
    def test_should_compress_large_data(self):
        """测试大数据应该压缩"""
        large_text = "x" * 200
        assert self.service.should_compress(large_text)
    
    def test_compress_decompress_roundtrip(self):
        """测试压缩解压往返"""
        original = "This is a test message " * 100
        
        # Compress
        compressed = self.service.compress(original)
        assert isinstance(compressed, bytes)
        assert len(compressed) < len(original.encode('utf-8'))
        
        # Decompress
        decompressed = self.service.decompress(compressed)
        assert decompressed == original
    
    def test_compress_empty_string(self):
        """测试空字符串"""
        result = self.service.compress("")
        assert result == b''
        
        decompressed = self.service.decompress(b'')
        assert decompressed == ''
    
    def test_compress_unicode(self):
        """测试 Unicode 字符"""
        original = "中文测试 🎉 " * 50
        compressed = self.service.compress(original)
        decompressed = self.service.decompress(compressed)
        assert decompressed == original
    
    def test_compress_if_needed_small(self):
        """测试智能压缩 - 小数据"""
        small_text = "Small"
        data, is_compressed = self.service.compress_if_needed(small_text)
        assert not is_compressed
        assert data == small_text.encode('utf-8')
    
    def test_compress_if_needed_large(self):
        """测试智能压缩 - 大数据"""
        large_text = "x" * 200
        data, is_compressed = self.service.compress_if_needed(large_text)
        assert is_compressed
        assert isinstance(data, bytes)
    
    def test_get_stats(self):
        """测试统计信息"""
        # Compress some data
        self.service.compress("test data " * 100)
        self.service.compress("more data " * 100)
        
        stats = self.service.get_stats()
        assert stats['compressed_count'] == 2
        assert stats['avg_compression_ratio'] > 1.0
        assert stats['space_saved_bytes'] > 0
    
    def test_reset_stats(self):
        """测试重置统计"""
        self.service.compress("test " * 100)
        self.service.reset_stats()
        
        stats = self.service.get_stats()
        assert stats['compressed_count'] == 0
        assert stats['total_original_bytes'] == 0
    
    def test_compression_error_handling(self):
        """测试压缩错误处理"""
        # Should not raise exception
        result = self.service.compress("test")
        assert isinstance(result, bytes)
    
    def test_decompression_uncompressed_data(self):
        """测试解压未压缩的数据"""
        # Should handle gracefully
        original = "test data"
        data = original.encode('utf-8')
        result = self.service.decompress(data)
        # Should return original or empty, not crash
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
