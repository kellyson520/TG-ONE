#!/usr/bin/env python3
"""
数据库迁移脚本：为 ForwardRule 表添加过滤器配置字段
"""
import os
import sys
import logging
from sqlalchemy import text, inspect

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.models import get_session, get_engine, ForwardRule
from filters.config_manager import get_filter_config_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_column_exists(table_name: str, column_name: str) -> bool:
    """检查表中是否存在指定列"""
    try:
        engine = get_engine()
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.error(f"检查列 {column_name} 是否存在时出错: {e}")
        return False


def add_column_if_not_exists(session, table_name: str, column_name: str, column_definition: str):
    """如果列不存在则添加"""
    if not check_column_exists(table_name, column_name):
        try:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            session.execute(text(sql))
            session.commit()
            logger.info(f"成功添加列: {table_name}.{column_name}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"添加列 {table_name}.{column_name} 失败: {e}")
            return False
    else:
        logger.info(f"列 {table_name}.{column_name} 已存在，跳过添加")
        return True


def migrate_database_schema():
    """迁移数据库结构"""
    logger.info("开始数据库结构迁移...")
    
    session = get_session()
    
    try:
        # 添加 enabled_filters 字段
        success1 = add_column_if_not_exists(
            session, 
            'forward_rules', 
            'enabled_filters', 
            'TEXT'
        )
        
        # 添加 user_mode_filters 字段（用于用户模式专用配置）
        success2 = add_column_if_not_exists(
            session,
            'forward_rules',
            'user_mode_filters',
            'TEXT'
        )
        
        if success1 and success2:
            logger.info("数据库结构迁移完成")
            return True
        else:
            logger.error("数据库结构迁移失败")
            return False
            
    except Exception as e:
        session.rollback()
        logger.error(f"数据库结构迁移异常: {e}")
        return False
    finally:
        session.close()


def migrate_rule_configurations():
    """迁移规则配置"""
    logger.info("开始规则配置迁移...")
    
    try:
        config_manager = get_filter_config_manager()
        result = config_manager.migrate_existing_rules()
        
        logger.info(f"规则配置迁移完成:")
        logger.info(f"  总规则数: {result['total_rules']}")
        logger.info(f"  成功迁移: {result['migrated_rules']}")
        logger.info(f"  失败规则: {result['failed_rules']}")
        
        if result['errors']:
            logger.warning("迁移过程中的错误:")
            for error in result['errors']:
                logger.warning(f"  - {error}")
        
        return result['failed_rules'] == 0
        
    except Exception as e:
        logger.error(f"规则配置迁移异常: {e}")
        return False


def create_sample_user_mode_configs():
    """为部分规则创建示例用户模式配置"""
    logger.info("创建示例用户模式配置...")
    
    session = get_session()
    
    try:
        # 获取前5个规则作为示例
        rules = session.query(ForwardRule).limit(5).all()
        
        # 不同的用户模式配置模板
        user_mode_templates = {
            "minimal": ["init", "keyword", "sender"],
            "basic": ["init", "keyword", "replace", "sender"],
            "delayed": ["init", "delay", "keyword", "sender"],
        }
        
        template_names = list(user_mode_templates.keys())
        
        for i, rule in enumerate(rules):
            if not hasattr(rule, 'user_mode_filters') or not rule.user_mode_filters:
                template_name = template_names[i % len(template_names)]
                template = user_mode_templates[template_name]
                
                import json
                config = {
                    "version": "1.0",
                    "filters": template,
                    "description": f"用户模式示例配置 - {template_name}",
                    "template": template_name
                }
                
                rule.user_mode_filters = json.dumps(config, ensure_ascii=False)
                logger.info(f"为规则 {rule.id} 设置用户模式配置: {template_name}")
        
        session.commit()
        logger.info(f"成功为 {len(rules)} 个规则创建示例用户模式配置")
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"创建示例用户模式配置失败: {e}")
        return False
    finally:
        session.close()


def validate_migration():
    """验证迁移结果"""
    logger.info("验证迁移结果...")
    
    session = get_session()
    
    try:
        # 检查字段是否添加成功
        enabled_filters_exists = check_column_exists('forward_rules', 'enabled_filters')
        user_mode_filters_exists = check_column_exists('forward_rules', 'user_mode_filters')
        
        if not enabled_filters_exists:
            logger.error("enabled_filters 字段未成功添加")
            return False
        
        if not user_mode_filters_exists:
            logger.error("user_mode_filters 字段未成功添加")
            return False
        
        # 检查配置迁移结果
        total_rules = session.query(ForwardRule).count()
        configured_rules = session.query(ForwardRule).filter(
            ForwardRule.enabled_filters.isnot(None),
            ForwardRule.enabled_filters != ''
        ).count()
        
        logger.info(f"验证结果:")
        logger.info(f"  总规则数: {total_rules}")
        logger.info(f"  已配置规则数: {configured_rules}")
        logger.info(f"  配置覆盖率: {configured_rules/total_rules*100:.1f}%" if total_rules > 0 else "  配置覆盖率: 0%")
        
        # 验证配置格式
        config_manager = get_filter_config_manager()
        sample_rules = session.query(ForwardRule).filter(
            ForwardRule.enabled_filters.isnot(None)
        ).limit(3).all()
        
        validation_success = True
        for rule in sample_rules:
            validation = config_manager.validate_rule_config(rule)
            if not validation['valid']:
                logger.warning(f"规则 {rule.id} 配置验证失败: {validation['errors']}")
                validation_success = False
        
        if validation_success:
            logger.info("✓ 配置验证通过")
        else:
            logger.warning("⚠ 部分配置验证失败")
        
        logger.info("✓ 迁移验证完成")
        return True
        
    except Exception as e:
        logger.error(f"迁移验证失败: {e}")
        return False
    finally:
        session.close()


def main():
    """主迁移函数"""
    logger.info("开始过滤器字段迁移...")
    
    steps = [
        ("数据库结构迁移", migrate_database_schema),
        ("规则配置迁移", migrate_rule_configurations),
        ("示例用户模式配置", create_sample_user_mode_configs),
        ("迁移验证", validate_migration),
    ]
    
    success_count = 0
    
    for step_name, step_func in steps:
        logger.info(f"\n{'='*50}")
        logger.info(f"执行步骤: {step_name}")
        logger.info(f"{'='*50}")
        
        try:
            if step_func():
                logger.info(f"✓ {step_name} 成功")
                success_count += 1
            else:
                logger.error(f"✗ {step_name} 失败")
        except Exception as e:
            logger.error(f"✗ {step_name} 异常: {e}")
            logger.exception("详细错误信息:")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"迁移完成: {success_count}/{len(steps)} 个步骤成功")
    logger.info(f"{'='*50}")
    
    if success_count == len(steps):
        logger.info("🎉 所有迁移步骤成功完成！")
        logger.info("\n下一步操作:")
        logger.info("1. 使用 python scripts/filter_management.py list 查看可用过滤器")
        logger.info("2. 使用 python scripts/filter_management.py validate <rule_id> 验证规则配置")
        logger.info("3. 重启应用以使新配置生效")
        return True
    else:
        logger.error("❌ 部分迁移步骤失败，请检查错误信息")
        return False


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n迁移被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"迁移脚本异常: {e}")
        logger.exception("详细错误信息:")
        sys.exit(1)
