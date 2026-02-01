"""
过滤器注册中心
管理所有可用的过滤器类，支持配置化流水线
"""
import logging
from typing import Dict, List, Type, Optional, Tuple
from filters.base_filter import BaseFilter

# 导入所有过滤器类
from filters.init_filter import InitFilter
from filters.global_filter import GlobalFilter
from filters.delay_filter import DelayFilter
from filters.keyword_filter import KeywordFilter
from filters.replace_filter import ReplaceFilter
from filters.media_filter import MediaFilter
from filters.advanced_media_filter import AdvancedMediaFilter
from filters.ai_filter import AIFilter
from filters.info_filter import InfoFilter
from filters.comment_button_filter import CommentButtonFilter
from filters.rss_filter import RSSFilter
from filters.edit_filter import EditFilter
from filters.sender_filter import SenderFilter
from filters.reply_filter import ReplyFilter
from filters.push_filter import PushFilter
from filters.delete_original_filter import DeleteOriginalFilter

logger = logging.getLogger(__name__)


class FilterRegistry:
    """过滤器注册中心"""
    
    def __init__(self):
        """初始化注册中心"""
        self._filters: Dict[str, Type[BaseFilter]] = {}
        self._default_order: List[str] = []
        self._filter_dependencies: Dict[str, List[str]] = {}
        self._register_default_filters()
    
    def _register_default_filters(self):
        """注册默认过滤器并设置执行顺序"""
        # 注册所有过滤器
        filter_classes = [
            ('init', InitFilter),
            ('global', GlobalFilter),
            ('delay', DelayFilter),
            ('keyword', KeywordFilter),
            ('replace', ReplaceFilter),
            ('media', MediaFilter),
            ('advanced_media', AdvancedMediaFilter),
            ('ai', AIFilter),
            ('info', InfoFilter),
            ('comment_button', CommentButtonFilter),
            ('rss', RSSFilter),
            ('edit', EditFilter),
            ('sender', SenderFilter),
            ('reply', ReplyFilter),
            ('push', PushFilter),
            ('delete_original', DeleteOriginalFilter),
        ]
        
        for name, filter_class in filter_classes:
            self.register(name, filter_class)
        
        # 设置默认执行顺序（与原有process.py中的顺序保持一致）
        self._default_order = [
            'init',           # 初始化过滤器
            'global',         # 全局过滤器
            'delay',          # 延迟处理过滤器
            'keyword',        # 关键字过滤器
            'replace',        # 替换过滤器
            'media',          # 媒体过滤器
            'advanced_media', # 高级媒体过滤器
            'ai',             # AI处理过滤器
            'info',           # 信息过滤器
            'comment_button', # 评论区按钮过滤器
            'rss',            # RSS过滤器
            'edit',           # 编辑过滤器
            'sender',         # 发送过滤器
            'reply',          # 回复过滤器
            'push',           # 推送过滤器
            'delete_original', # 删除原始消息过滤器（最后执行）
        ]
        
        # 设置过滤器依赖关系（可选，用于验证配置）
        # 注意：依赖关系应该是必需的依赖，而不是建议的依赖
        self._filter_dependencies = {
            'reply': ['sender'],                               # 回复过滤器依赖于发送过滤器
            'delete_original': ['sender'],                     # 删除原始消息依赖于发送完成
        }
    
    def register(self, name: str, filter_class: Type[BaseFilter]) -> None:
        """
        注册过滤器
        
        Args:
            name: 过滤器名称
            filter_class: 过滤器类
        """
        if not issubclass(filter_class, BaseFilter):
            raise TypeError(f"过滤器 {name} 必须是 BaseFilter 的子类")
        
        self._filters[name] = filter_class
        logger.debug(f"注册过滤器: {name} -> {filter_class.__name__}")
    
    def get_filter(self, name: str) -> Optional[Type[BaseFilter]]:
        """
        获取过滤器类
        
        Args:
            name: 过滤器名称
            
        Returns:
            过滤器类或None
        """
        return self._filters.get(name)
    
    def create_filter(self, name: str) -> Optional[BaseFilter]:
        """
        创建过滤器实例
        
        Args:
            name: 过滤器名称
            
        Returns:
            过滤器实例或None
        """
        filter_class = self.get_filter(name)
        if filter_class:
            return filter_class()
        return None
    
    def get_all_filters(self) -> Dict[str, Type[BaseFilter]]:
        """获取所有注册的过滤器"""
        return self._filters.copy()
    
    def get_default_order(self) -> List[str]:
        """获取默认的过滤器执行顺序"""
        return self._default_order.copy()
    
    def validate_filter_config(self, enabled_filters: List[str]) -> Tuple[bool, List[str]]:
        """
        验证过滤器配置
        
        Args:
            enabled_filters: 启用的过滤器列表
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        # 检查所有过滤器是否已注册
        for filter_name in enabled_filters:
            if filter_name not in self._filters:
                errors.append(f"未知的过滤器: {filter_name}")
        
        # 检查依赖关系
        for filter_name in enabled_filters:
            dependencies = self._filter_dependencies.get(filter_name, [])
            for dep in dependencies:
                if dep not in enabled_filters:
                    errors.append(f"过滤器 {filter_name} 依赖于 {dep}，但 {dep} 未启用")
        
        return len(errors) == 0, errors
    
    def optimize_filter_order(self, enabled_filters: List[str]) -> List[str]:
        """
        根据默认顺序和依赖关系优化过滤器执行顺序
        
        Args:
            enabled_filters: 启用的过滤器列表
            
        Returns:
            优化后的过滤器执行顺序
        """
        # 按默认顺序排序已启用的过滤器
        ordered_filters = []
        for filter_name in self._default_order:
            if filter_name in enabled_filters:
                ordered_filters.append(filter_name)
        
        # 添加不在默认顺序中但已启用的过滤器
        for filter_name in enabled_filters:
            if filter_name not in ordered_filters:
                ordered_filters.append(filter_name)
        
        return ordered_filters
    
    def get_filter_info(self) -> Dict[str, Dict]:
        """
        获取所有过滤器的信息
        
        Returns:
            过滤器信息字典
        """
        info = {}
        for name, filter_class in self._filters.items():
            info[name] = {
                'name': name,
                'class_name': filter_class.__name__,
                'description': filter_class.__doc__ or "无描述",
                'dependencies': self._filter_dependencies.get(name, []),
                'default_order_index': self._default_order.index(name) if name in self._default_order else -1
            }
        return info


# 全局注册中心实例
filter_registry = FilterRegistry()


def get_filter_registry() -> FilterRegistry:
    """获取全局过滤器注册中心实例"""
    return filter_registry
