"""
过滤器配置管理器
负责默认配置、规则迁移和配置管理
"""
import json
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from models.models import ForwardRule, SessionManager
from filters.registry import get_filter_registry
from filters.factory import get_filter_chain_factory

logger = logging.getLogger(__name__)


class FilterConfigManager:
    """过滤器配置管理器"""
    
    def __init__(self):
        """初始化配置管理器"""
        self._registry = get_filter_registry()
        self._factory = get_filter_chain_factory()
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        获取默认过滤器配置
        
        Returns:
            默认配置字典
        """
        return {
            "version": "1.0",
            "filters": self._registry.get_default_order(),
            "description": "默认过滤器链配置",
            "created_by": "system"
        }
    
    def migrate_filter_configs(self, session: Optional[Session] = None) -> Dict[str, Any]:
        """
        迁移现有规则到新的配置化过滤器链
        
        Args:
            session: 数据库会话，如果为None则创建新会话
            
        Returns:
            迁移结果统计
        """
        if session is None:
            with SessionManager() as session:
                return self.migrate_filter_configs(session)
        
        try:
            # 获取所有没有enabled_filters配置的规则
            rules = session.query(ForwardRule).filter(
                (ForwardRule.enabled_filters.is_(None)) | 
                (ForwardRule.enabled_filters == '')
            ).all()
            
            migration_stats = {
                "total_rules": len(rules),
                "migrated_rules": 0,
                "failed_rules": 0,
                "errors": []
            }
            
            for rule in rules:
                try:
                    # 基于现有字段生成过滤器配置
                    filter_config = self._generate_config_for_rule(rule)
                    rule.enabled_filters = json.dumps(filter_config, ensure_ascii=False)
                    migration_stats["migrated_rules"] += 1
                    logger.info(f"成功迁移规则 {rule.id} 的过滤器配置")
                    
                except Exception as e:
                    migration_stats["failed_rules"] += 1
                    error_msg = f"迁移规则 {rule.id} 失败: {str(e)}"
                    migration_stats["errors"].append(error_msg)
                    logger.error(error_msg)
            
            # 提交更改
            session.commit()
            logger.info(f"过滤器配置迁移完成: {migration_stats}")
            return migration_stats
            
        except Exception as e:
            session.rollback()
            logger.error(f"迁移过程中发生错误: {str(e)}")
            raise
    
    def _generate_config_for_rule(self, rule: ForwardRule) -> Dict[str, Any]:
        """
        基于规则现有字段生成过滤器配置
        
        Args:
            rule: 转发规则
            
        Returns:
            生成的过滤器配置
        """
        enabled_filters = []
        default_order = self._registry.get_default_order()
        
        # 根据规则字段决定启用的过滤器
        filter_conditions = {
            'init': True,  # 初始化过滤器总是启用
            'global': True,  # 全局过滤器总是启用
            'delay': rule.enable_delay,
            'keyword': True,  # 关键字过滤器总是启用
            'replace': rule.is_replace,
            'media': self._should_enable_media_filter(rule),
            'advanced_media': self._should_enable_advanced_media_filter(rule),
            'ai': rule.is_ai,
            'info': True,  # 信息过滤器总是启用
            'comment_button': rule.enable_comment_button,
            'rss': rule.only_rss,
            'edit': rule.handle_mode.value == 'edit' if hasattr(rule.handle_mode, 'value') else False,
            'sender': True,  # 发送过滤器总是启用
            'reply': True,  # 回复过滤器总是启用
            'push': rule.enable_push,
            'delete_original': rule.is_delete_original,
        }
        
        # 按默认顺序添加启用的过滤器
        for filter_name in default_order:
            if filter_conditions.get(filter_name, False):
                enabled_filters.append(filter_name)
        
        return {
            "version": "1.0",
            "filters": enabled_filters,
            "description": f"基于规则 {rule.id} 现有配置生成",
            "migrated_from_legacy": True,
            "migration_timestamp": None  # 可以在实际使用时添加时间戳
        }
    
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
    
    def validate_rule_config(self, rule: ForwardRule) -> Dict[str, Any]:
        """
        验证规则的过滤器配置
        
        Args:
            rule: 转发规则
            
        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "config": None
        }
        
        try:
            if not rule.enabled_filters:
                result["warnings"].append("规则没有配置过滤器链，将使用默认配置")
                result["config"] = self.get_default_config()
                return result
            
            # 解析配置
            if isinstance(rule.enabled_filters, str):
                config = json.loads(rule.enabled_filters)
            else:
                config = rule.enabled_filters
            
            result["config"] = config
            
            # 验证配置结构
            if not isinstance(config, dict):
                result["valid"] = False
                result["errors"].append("配置格式不正确，应为JSON对象")
                return result
            
            # 获取过滤器列表
            filters = config.get("filters", [])
            if not isinstance(filters, list):
                result["valid"] = False
                result["errors"].append("filters字段应为数组")
                return result
            
            # 验证过滤器
            is_valid, errors = self._registry.validate_filter_config(filters)
            if not is_valid:
                result["valid"] = False
                result["errors"].extend(errors)
            
            # 检查是否有推荐的优化
            optimized_filters = self._registry.optimize_filter_order(filters)
            if optimized_filters != filters:
                result["warnings"].append("过滤器顺序可以优化")
            
        except json.JSONDecodeError as e:
            result["valid"] = False
            result["errors"].append(f"JSON格式错误: {str(e)}")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"验证过程中发生错误: {str(e)}")
        
        return result
    
    def get_rule_filter_info(self, rule: ForwardRule) -> Dict[str, Any]:
        """
        获取规则的过滤器信息
        
        Args:
            rule: 转发规则
            
        Returns:
            过滤器信息
        """
        validation = self.validate_rule_config(rule)
        
        info = {
            "rule_id": rule.id,
            "validation": validation,
            "available_filters": self._registry.get_filter_info(),
            "default_order": self._registry.get_default_order(),
            "factory_cache_stats": self._factory.get_cache_stats()
        }
        
        if validation["valid"] and validation["config"]:
            config = validation["config"]
            enabled_filters = config.get("filters", [])
            optimized_filters = self._registry.optimize_filter_order(enabled_filters)
            
            info.update({
                "enabled_filters": enabled_filters,
                "optimized_order": optimized_filters,
                "filter_count": len(enabled_filters)
            })
        
        return info
    
    def save_filter_config(self, rule_id: int, filter_config: Dict[str, Any], session: Optional[Session] = None) -> bool:
        """
        保存过滤器配置
        
        Args:
            rule_id: 规则ID
            filter_config: 过滤器配置
            session: 可选的数据库会话
        
        Returns:
            是否保存成功
        """
        if session is None:
            with SessionManager() as session:
                return self.save_filter_config(rule_id, filter_config, session)
        
        try:
            rule = session.query(ForwardRule).filter_by(id=rule_id).first()
            if not rule:
                logger.error(f"规则 {rule_id} 不存在")
                return False
            
            # 验证配置
            old_enabled_filters = rule.enabled_filters
            rule.enabled_filters = json.dumps(filter_config, ensure_ascii=False)
            
            validation = self.validate_rule_config(rule)
            if not validation["valid"]:
                logger.error(f"配置验证失败: {validation['errors']}")
                rule.enabled_filters = old_enabled_filters
                return False
            
            # 清除相关的缓存
            self._factory.clear_cache()
            
            # 提交更改
            session.commit()
            logger.info(f"成功更新规则 {rule_id} 的过滤器配置")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"更新规则 {rule_id} 配置失败: {str(e)}")
            return False
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局过滤器配置"""
        return {
            "disabled_filters": self._factory.get_global_disabled_filters(),
            "available_filters": list(self._registry.get_all_filters().keys()),
            "default_order": self._registry.get_default_order(),
            "cache_stats": self._factory.get_cache_stats()
        }
    
    def update_global_config(self, disabled_filters: List[str]) -> bool:
        """
        更新全局过滤器配置
        
        Args:
            disabled_filters: 全局禁用的过滤器列表
            
        Returns:
            是否更新成功
        """
        try:
            # 验证过滤器名称
            available_filters = set(self._registry.get_all_filters().keys())
            invalid_filters = [f for f in disabled_filters if f not in available_filters]
            
            if invalid_filters:
                logger.error(f"无效的过滤器名称: {invalid_filters}")
                return False
            
            self._factory.set_global_disabled_filters(disabled_filters)
            logger.info(f"成功更新全局禁用过滤器: {disabled_filters}")
            return True
            
        except Exception as e:
            logger.error(f"更新全局配置失败: {str(e)}")
            return False


# 全局配置管理器实例
filter_config_manager = FilterConfigManager()


def get_filter_config_manager() -> FilterConfigManager:
    """获取全局过滤器配置管理器实例"""
    return filter_config_manager
