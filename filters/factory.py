"""
过滤器链工厂
负责基于配置创建和缓存过滤器链实例
"""
import logging
import json
from typing import Dict, List, Optional, Any
from filters.filter_chain import FilterChain
from filters.registry import get_filter_registry
from models.models import ForwardRule

logger = logging.getLogger(__name__)


class FilterChainFactory:
    """过滤器链工厂类"""
    
    def __init__(self):
        """初始化工厂"""
        self._chain_cache: Dict[str, FilterChain] = {}
        self._registry = get_filter_registry()
        self._global_disabled_filters: set = set()
        self._global_config_cache: Dict[str, Any] = {}
    
    def set_global_disabled_filters(self, disabled_filters: List[str]) -> None:
        """
        设置全局禁用的过滤器
        
        Args:
            disabled_filters: 全局禁用的过滤器名称列表
        """
        self._global_disabled_filters = set(disabled_filters)
        # 清空缓存，因为全局配置已更改
        self._chain_cache.clear()
        logger.info(f"设置全局禁用过滤器: {disabled_filters}")
    
    def get_global_disabled_filters(self) -> List[str]:
        """获取全局禁用的过滤器列表"""
        return list(self._global_disabled_filters)
    
    def create_chain_for_rule(self, rule: ForwardRule, use_cache: bool = True) -> FilterChain:
        """
        为指定规则创建过滤器链
        
        Args:
            rule: 转发规则
            use_cache: 是否使用缓存
            
        Returns:
            过滤器链实例
        """
        # 生成缓存键
        cache_key = self._generate_cache_key(rule)
        
        # 检查缓存
        if use_cache and cache_key in self._chain_cache:
            logger.debug(f"使用缓存的过滤器链: {cache_key}")
            return self._chain_cache[cache_key]
        
        # 获取规则的过滤器配置
        enabled_filters = self._get_enabled_filters_for_rule(rule)
        
        # 应用全局禁用过滤器
        enabled_filters = [f for f in enabled_filters if f not in self._global_disabled_filters]
        
        # 验证配置
        is_valid, errors = self._registry.validate_filter_config(enabled_filters)
        if not is_valid:
            logger.warning(f"规则 {rule.id} 的过滤器配置无效: {errors}")
            # 回退到默认配置
            enabled_filters = self._get_default_filters_for_rule(rule)
        
        # 优化过滤器顺序
        optimized_filters = self._registry.optimize_filter_order(enabled_filters)
        
        # 创建过滤器链
        chain = self._create_chain(optimized_filters)
        
        # 缓存链实例
        if use_cache:
            self._chain_cache[cache_key] = chain
            logger.debug(f"缓存过滤器链: {cache_key} -> {optimized_filters}")
        
        return chain
    
    def _generate_cache_key(self, rule: ForwardRule) -> str:
        """
        生成规则的缓存键
        
        Args:
            rule: 转发规则
            
        Returns:
            缓存键字符串
        """
        # 基于规则配置生成唯一键
        config_items = [
            f"rule_id:{rule.id}",
            f"enabled_filters:{getattr(rule, 'enabled_filters', '')}",
            f"global_disabled:{sorted(self._global_disabled_filters)}",
            # 添加影响过滤器行为的主要字段
            f"enable_rule:{rule.enable_rule}",
            f"is_ai:{rule.is_ai}",
            f"enable_delay:{rule.enable_delay}",
            f"enable_media_type_filter:{rule.enable_media_type_filter}",
            f"enable_push:{rule.enable_push}",
            f"only_rss:{rule.only_rss}",
            f"is_delete_original:{rule.is_delete_original}",
        ]
        
        return "|".join(config_items)
    
    def _get_enabled_filters_for_rule(self, rule: ForwardRule) -> List[str]:
        """
        获取规则启用的过滤器列表
        
        Args:
            rule: 转发规则
            
        Returns:
            启用的过滤器名称列表
        """
        # 首先检查是否有显式的过滤器配置
        if hasattr(rule, 'enabled_filters') and rule.enabled_filters:
            try:
                # 尝试解析JSON配置
                if isinstance(rule.enabled_filters, str):
                    config = json.loads(rule.enabled_filters)
                else:
                    config = rule.enabled_filters
                
                if isinstance(config, list):
                    return config
                elif isinstance(config, dict) and 'filters' in config:
                    return config['filters']
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"解析规则 {rule.id} 的enabled_filters配置失败: {e}")
        
        # 回退到基于现有字段的逻辑推导
        return self._get_default_filters_for_rule(rule)
    
    def _get_default_filters_for_rule(self, rule: ForwardRule) -> List[str]:
        """
        基于规则现有字段推导默认的过滤器配置
        
        Args:
            rule: 转发规则
            
        Returns:
            默认启用的过滤器列表
        """
        enabled_filters = []
        
        # 获取默认顺序
        default_order = self._registry.get_default_order()
        
        # 根据规则设置决定启用哪些过滤器
        for filter_name in default_order:
            should_enable = True
            
            # 基于规则字段判断是否启用特定过滤器
            if filter_name == 'delay' and not rule.enable_delay:
                should_enable = False
            elif filter_name == 'ai' and not rule.is_ai:
                should_enable = False
            elif filter_name == 'push' and not rule.enable_push:
                should_enable = False
            elif filter_name == 'rss' and not rule.only_rss:
                should_enable = False
            elif filter_name == 'delete_original' and not rule.is_delete_original:
                should_enable = False
            elif filter_name == 'comment_button' and not rule.enable_comment_button:
                should_enable = False
            elif filter_name == 'media' and not self._should_enable_media_filter(rule):
                should_enable = False
            elif filter_name == 'advanced_media' and not self._should_enable_advanced_media_filter(rule):
                should_enable = False
            
            if should_enable:
                enabled_filters.append(filter_name)
        
        return enabled_filters
    
    def _should_enable_media_filter(self, rule: ForwardRule) -> bool:
        """判断是否应该启用媒体过滤器"""
        return (rule.enable_media_type_filter or 
                rule.enable_media_size_filter or 
                rule.enable_extension_filter)
    
    def _should_enable_advanced_media_filter(self, rule: ForwardRule) -> bool:
        """判断是否应该启用高级媒体过滤器"""
        return (rule.enable_duration_filter or 
                rule.enable_resolution_filter or 
                rule.enable_file_size_range)
    
    def _create_chain(self, enabled_filters: List[str]) -> FilterChain:
        """
        创建过滤器链
        
        Args:
            enabled_filters: 启用的过滤器名称列表
            
        Returns:
            过滤器链实例
        """
        chain = FilterChain()
        
        for filter_name in enabled_filters:
            filter_instance = self._registry.create_filter(filter_name)
            if filter_instance:
                chain.add_filter(filter_instance)
                logger.debug(f"添加过滤器到链: {filter_name}")
            else:
                logger.warning(f"无法创建过滤器: {filter_name}")
        
        return chain
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._chain_cache.clear()
        logger.info("已清空过滤器链缓存")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'cache_size': len(self._chain_cache),
            'cached_keys': list(self._chain_cache.keys()),
            'global_disabled_filters': list(self._global_disabled_filters)
        }
    
    def create_chain_from_config(self, filter_config: List[str], use_cache: bool = False) -> FilterChain:
        """
        根据过滤器配置直接创建链
        
        Args:
            filter_config: 过滤器名称列表
            use_cache: 是否使用缓存
            
        Returns:
            过滤器链实例
        """
        if use_cache:
            cache_key = f"custom:{','.join(filter_config)}"
            if cache_key in self._chain_cache:
                return self._chain_cache[cache_key]
        
        # 应用全局禁用过滤器
        enabled_filters = [f for f in filter_config if f not in self._global_disabled_filters]
        
        # 验证和优化配置
        is_valid, errors = self._registry.validate_filter_config(enabled_filters)
        if not is_valid:
            logger.warning(f"自定义过滤器配置无效: {errors}")
        
        optimized_filters = self._registry.optimize_filter_order(enabled_filters)
        chain = self._create_chain(optimized_filters)
        
        if use_cache:
            self._chain_cache[cache_key] = chain
        
        return chain


# 全局工厂实例
filter_chain_factory = FilterChainFactory()


def get_filter_chain_factory() -> FilterChainFactory:
    """获取全局过滤器链工厂实例"""
    return filter_chain_factory
