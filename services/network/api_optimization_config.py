"""
API优化配置管理
提供统一的优化开关和回退机制配置
"""

import logging
from core.config import settings

logger = logging.getLogger(__name__)


class APIOptimizationConfig:
    """API优化配置管理器 (已重构为 Settings 的代理)"""

    def __init__(self):
        self._load_config()

    def _load_config(self):
        """加载配置"""
        # 从全局 settings 同步状态
        self.ENABLE_KEYWORD_SEARCH_API = settings.ENABLE_KEYWORD_SEARCH_API
        self.ENABLE_MEDIA_INFO_OPTIMIZATION = settings.ENABLE_MEDIA_INFO_OPTIMIZATION
        self.ENABLE_BATCH_FORWARD_API = settings.ENABLE_BATCH_FORWARD_API
        
        self.MAX_BATCH_SIZE = settings.FORWARD_MAX_BATCH_SIZE
        self.MIN_BATCH_SIZE = settings.FORWARD_MIN_BATCH_SIZE
        
        self.MEDIA_SAMPLE_SIZE = settings.MEDIA_SAMPLE_SIZE
        self.ENABLE_MEDIA_CACHE = settings.ENABLE_MEDIA_CACHE
        
        self.SEARCH_CACHE_TTL = settings.SEARCH_CACHE_TTL
        self.MAX_SEARCH_RESULTS = settings.MAX_SEARCH_RESULTS
        
        self.ENABLE_AUTO_FALLBACK = settings.ENABLE_AUTO_FALLBACK
        self.FALLBACK_TIMEOUT = settings.API_FALLBACK_TIMEOUT
        self.MAX_API_RETRIES = settings.MAX_API_RETRIES
        
        self.ENABLE_PERFORMANCE_MONITORING = settings.ENABLE_PERFORMANCE_MONITORING

        logger.info("API优化配置已从全局 Settings 同步")
        self._log_config()

    def _log_config(self):
        """记录配置信息"""
        if not self.ENABLE_PERFORMANCE_MONITORING:
            return

        logger.info("=== API优化配置 ===")
        logger.info(f"关键词搜索API优化: {self.ENABLE_KEYWORD_SEARCH_API}")
        logger.info(f"媒体信息优化: {self.ENABLE_MEDIA_INFO_OPTIMIZATION}")
        logger.info(f"批量转发API: {self.ENABLE_BATCH_FORWARD_API}")
        logger.info(f"批量大小范围: {self.MIN_BATCH_SIZE}-{self.MAX_BATCH_SIZE}")
        logger.info(f"自动回退机制: {self.ENABLE_AUTO_FALLBACK}")
        logger.info(f"性能监控: {self.ENABLE_PERFORMANCE_MONITORING}")
        logger.info("==================")

    def is_keyword_search_enabled(self) -> bool:
        """是否启用关键词搜索API优化"""
        return self.ENABLE_KEYWORD_SEARCH_API

    def is_media_optimization_enabled(self) -> bool:
        """是否启用媒体处理优化"""
        return self.ENABLE_MEDIA_INFO_OPTIMIZATION

    def is_batch_forward_enabled(self) -> bool:
        """是否启用批量转发优化"""
        return self.ENABLE_BATCH_FORWARD_API

    def should_use_batch_forward(self, message_count: int) -> bool:
        """判断是否应该使用批量转发"""
        return (
            self.ENABLE_BATCH_FORWARD_API
            and self.MIN_BATCH_SIZE <= message_count <= self.MAX_BATCH_SIZE
        )

    def is_auto_fallback_enabled(self) -> bool:
        """是否启用自动回退机制"""
        return self.ENABLE_AUTO_FALLBACK

    def get_fallback_timeout(self) -> int:
        """获取回退超时时间"""
        return self.FALLBACK_TIMEOUT

    def get_max_retries(self) -> int:
        """获取最大重试次数"""
        return self.MAX_API_RETRIES

    def get_media_sample_size(self) -> int:
        """获取媒体采样大小"""
        return self.MEDIA_SAMPLE_SIZE

    def is_media_cache_enabled(self) -> bool:
        """是否启用媒体缓存"""
        return self.ENABLE_MEDIA_CACHE

    def get_search_cache_ttl(self) -> int:
        """获取搜索缓存TTL"""
        return self.SEARCH_CACHE_TTL

    def get_max_search_results(self) -> int:
        """获取最大搜索结果数"""
        return self.MAX_SEARCH_RESULTS

    def reload_config(self):
        """重新加载配置"""
        self._load_config()
        logger.info("API优化配置已重新加载")

    def get_optimization_summary(self) -> dict:
        """获取优化配置摘要"""
        return {
            "keyword_search_api": self.ENABLE_KEYWORD_SEARCH_API,
            "media_optimization": self.ENABLE_MEDIA_INFO_OPTIMIZATION,
            "batch_forward_api": self.ENABLE_BATCH_FORWARD_API,
            "auto_fallback": self.ENABLE_AUTO_FALLBACK,
            "performance_monitoring": self.ENABLE_PERFORMANCE_MONITORING,
            "batch_size_range": f"{self.MIN_BATCH_SIZE}-{self.MAX_BATCH_SIZE}",
            "fallback_timeout": self.FALLBACK_TIMEOUT,
            "max_retries": self.MAX_API_RETRIES,
        }


# 全局配置实例
api_optimization_config = APIOptimizationConfig()
