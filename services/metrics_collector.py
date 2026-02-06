"""
Metrics Collection Service
收集和暴露系统性能指标
"""
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """延迟指标"""
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    samples: list = field(default_factory=list)
    
    def record(self, latency_ms: float):
        """记录一次延迟"""
        self.count += 1
        self.total_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)
        
        # 保留最近1000个样本用于百分位计算
        self.samples.append(latency_ms)
        if len(self.samples) > 1000:
            self.samples.pop(0)
        
        # 更新百分位
        if self.samples:
            sorted_samples = sorted(self.samples)
            self.p50_ms = sorted_samples[len(sorted_samples) // 2]
            self.p95_ms = sorted_samples[int(len(sorted_samples) * 0.95)]
            self.p99_ms = sorted_samples[int(len(sorted_samples) * 0.99)]
    
    @property
    def avg_ms(self) -> float:
        """平均延迟"""
        return self.total_ms / self.count if self.count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "count": self.count,
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float('inf') else 0.0,
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2)
        }


class MetricsCollector:
    """
    系统指标收集器
    
    收集的指标:
    - 压缩统计
    - 限流统计
    - I/O 延迟分布
    - 系统资源使用
    """
    
    def __init__(self):
        self._compression_metrics: Optional[Dict] = None
        self._rate_limit_metrics: Dict[str, Dict] = {}
        self._io_latency: Dict[str, LatencyMetrics] = {
            "db_read": LatencyMetrics(),
            "db_write": LatencyMetrics(),
            "api_call": LatencyMetrics(),
            "file_io": LatencyMetrics()
        }
        self._start_time = time.time()
        self._custom_metrics: Dict[str, Any] = {}
        # 差分日志缓存：记录上一次成功打印的指标值
        self._last_logged_metrics: Dict[str, Any] = {}
        self._last_log_time = 0
    
    def record_compression_stats(self, stats: Dict[str, Any]):
        """记录压缩统计"""
        self._compression_metrics = stats
    
    def record_rate_limit_stats(self, name: str, stats: Dict[str, Any]):
        """记录限流统计"""
        self._rate_limit_metrics[name] = stats
    
    def record_io_latency(self, operation: str, latency_ms: float):
        """
        记录 I/O 延迟
        
        Args:
            operation: 操作类型 (db_read, db_write, api_call, file_io)
            latency_ms: 延迟时间 (毫秒)
        """
        if operation in self._io_latency:
            self._io_latency[operation].record(latency_ms)
        else:
            logger.warning(f"Unknown I/O operation: {operation}")
    
    def set_custom_metric(self, key: str, value: Any):
        """设置自定义指标"""
        self._custom_metrics[key] = value
    
    def get_compression_metrics(self) -> Dict[str, Any]:
        """获取压缩指标"""
        if self._compression_metrics is None:
            # 尝试从 compression_service 获取
            try:
                from services.compression_service import compression_service
                self._compression_metrics = compression_service.get_stats()
            except Exception as e:
                logger.error(f"Failed to get compression stats: {e}")
                return {}
        
        return self._compression_metrics or {}
    
    def get_rate_limit_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取限流指标"""
        # 尝试从 RateLimiterPool 获取最新数据
        try:
            from services.rate_limiter import RateLimiterPool
            self._rate_limit_metrics = RateLimiterPool.get_all_stats()
        except Exception as e:
            logger.error(f"Failed to get rate limit stats: {e}")
        
        return self._rate_limit_metrics
    
    def get_io_latency_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取 I/O 延迟指标"""
        return {
            operation: metrics.to_dict()
            for operation, metrics in self._io_latency.items()
        }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标 (带差分过滤逻辑)"""
        import psutil
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            current = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": round(memory.available / (1024 * 1024), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "uptime_seconds": int(time.time() - self._start_time)
            }

            # 差分检查逻辑
            should_log = False
            now = time.time()
            
            # 每 60 秒强制心跳打印一次
            if now - self._last_log_time > 60:
                should_log = True
            else:
                # 检查主要指标变化率 (变化 > 5% 则打印)
                for key in ["cpu_percent", "memory_percent"]:
                    old_val = self._last_logged_metrics.get(key)
                    if old_val is None:
                        should_log = True
                        break
                    
                    # 防止除以零
                    if old_val == 0:
                        if current[key] > 5:
                            should_log = True
                            break
                        continue
                        
                    change_rate = abs(current[key] - old_val) / old_val
                    if change_rate > 0.05:
                        should_log = True
                        break
            
            if should_log:
                # 仅在有显著变化或达到心跳时间时打印
                logger.info(f"🚀 [系统监控] CPU: {current['cpu_percent']}% | 内存: {current['memory_percent']}% | 磁盘: {current['disk_percent']}%")
                self._last_logged_metrics = current.copy()
                self._last_log_time = now
                
            return current
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {
                "uptime_seconds": int(time.time() - self._start_time)
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "compression": self.get_compression_metrics(),
            "rate_limit": self.get_rate_limit_metrics(),
            "io_latency": self.get_io_latency_metrics(),
            "system": self.get_system_metrics(),
            "custom": self._custom_metrics
        }
    
    def reset_all(self):
        """重置所有指标"""
        self._compression_metrics = None
        self._rate_limit_metrics = {}
        for metrics in self._io_latency.values():
            metrics.count = 0
            metrics.total_ms = 0.0
            metrics.min_ms = float('inf')
            metrics.max_ms = 0.0
            metrics.samples = []
        self._custom_metrics = {}
        
        # 重置服务层统计
        try:
            from services.compression_service import compression_service
            compression_service.reset_stats()
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        
        try:
            from services.rate_limiter import RateLimiterPool
            RateLimiterPool.reset_all_stats()
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')


# 全局单例
metrics_collector = MetricsCollector()
