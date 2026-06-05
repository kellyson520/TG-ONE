"""
Unit Tests: Metrics Collector
"""
import pytest
from services.metrics_collector import MetricsCollector, LatencyMetrics


class TestLatencyMetrics:
    """测试延迟指标"""
    
    def test_record_latency(self):
        """测试记录延迟"""
        metrics = LatencyMetrics()
        
        metrics.record(10.5)
        metrics.record(20.3)
        metrics.record(15.7)
        
        assert metrics.count == 3
        assert metrics.min_ms == 10.5
        assert metrics.max_ms == 20.3
        assert metrics.avg_ms == pytest.approx((10.5 + 20.3 + 15.7) / 3)
    
    def test_percentiles(self):
        """测试百分位计算"""
        metrics = LatencyMetrics()
        
        # Add 100 samples
        for i in range(100):
            metrics.record(float(i))
        
        assert metrics.p50_ms == pytest.approx(50.0, abs=1.0)
        assert metrics.p95_ms == pytest.approx(95.0, abs=1.0)
        assert metrics.p99_ms == pytest.approx(99.0, abs=1.0)
    
    def test_to_dict(self):
        """测试转换为字典"""
        metrics = LatencyMetrics()
        metrics.record(10.0)
        metrics.record(20.0)
        
        data = metrics.to_dict()
        assert 'count' in data
        assert 'avg_ms' in data
        assert 'p50_ms' in data
        assert data['count'] == 2


class TestMetricsCollector:
    """测试指标收集器"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.collector = MetricsCollector()
    
    def test_record_compression_stats(self):
        """测试记录压缩统计"""
        stats = {
            'compressed_count': 10,
            'avg_compression_ratio': 5.0,
            'space_saved_bytes': 1000
        }
        
        self.collector.record_compression_stats(stats)
        result = self.collector.get_compression_metrics()
        
        assert result['compressed_count'] == 10
        assert result['avg_compression_ratio'] == 5.0
    
    def test_record_rate_limit_stats(self):
        """测试记录限流统计"""
        stats = {
            'total_requests': 100,
            'accepted_requests': 90,
            'rejected_requests': 10
        }
        
        self.collector.record_rate_limit_stats("db_writes", stats)
        
        # Check internal state directly
        assert "db_writes" in self.collector._rate_limit_metrics
        assert self.collector._rate_limit_metrics["db_writes"]["total_requests"] == 100
    
    def test_record_io_latency(self):
        """测试记录 I/O 延迟"""
        self.collector.record_io_latency("db_read", 10.5)
        self.collector.record_io_latency("db_read", 15.3)
        
        metrics = self.collector.get_io_latency_metrics()
        assert "db_read" in metrics
        assert metrics["db_read"]["count"] == 2
    
    def test_set_custom_metric(self):
        """测试设置自定义指标"""
        self.collector.set_custom_metric("test_key", "test_value")
        
        all_metrics = self.collector.get_all_metrics()
        assert all_metrics["custom"]["test_key"] == "test_value"
    
    def test_get_all_metrics(self):
        """测试获取所有指标"""
        self.collector.record_io_latency("db_write", 5.0)
        self.collector.set_custom_metric("version", "1.0.0")
        
        all_metrics = self.collector.get_all_metrics()
        
        assert "timestamp" in all_metrics
        assert "compression" in all_metrics
        assert "rate_limit" in all_metrics
        assert "io_latency" in all_metrics
        assert "system" in all_metrics
        assert "custom" in all_metrics
    
    def test_reset_all(self):
        """测试重置所有指标"""
        self.collector.record_io_latency("db_read", 10.0)
        self.collector.set_custom_metric("test", "value")
        
        self.collector.reset_all()
        
        metrics = self.collector.get_io_latency_metrics()
        assert metrics["db_read"]["count"] == 0
        
        all_metrics = self.collector.get_all_metrics()
        assert len(all_metrics["custom"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
