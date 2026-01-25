#!/usr/bin/env python3
"""
过滤器管理脚本
用于迁移现有规则、管理配置和验证过滤器链
"""
import os
import sys
import json
import argparse
import logging
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.models import get_session, ForwardRule
from filters.config_manager import get_filter_config_manager
from filters.registry import get_filter_registry
from filters.factory import get_filter_chain_factory

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_rules():
    """迁移现有规则到新的配置化过滤器链"""
    print("开始迁移现有规则...")
    
    config_manager = get_filter_config_manager()
    session = get_session()
    
    try:
        result = config_manager.migrate_existing_rules(session)
        
        print(f"迁移完成！")
        print(f"总规则数: {result['total_rules']}")
        print(f"成功迁移: {result['migrated_rules']}")
        print(f"失败规则: {result['failed_rules']}")
        
        if result['errors']:
            print("\n错误信息:")
            for error in result['errors']:
                print(f"  - {error}")
        
        return True
        
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        return False
    finally:
        session.close()


def list_filters():
    """列出所有可用的过滤器"""
    print("可用的过滤器:")
    
    registry = get_filter_registry()
    filter_info = registry.get_filter_info()
    default_order = registry.get_default_order()
    
    print(f"\n默认执行顺序:")
    for i, filter_name in enumerate(default_order, 1):
        info = filter_info.get(filter_name, {})
        print(f"  {i:2d}. {filter_name:15s} - {info.get('class_name', 'Unknown')}")
        if info.get('dependencies'):
            print(f"      依赖: {', '.join(info['dependencies'])}")
    
    print(f"\n所有已注册过滤器:")
    for name, info in sorted(filter_info.items()):
        status = "✓" if name in default_order else " "
        print(f"  {status} {name:15s} - {info.get('description', '无描述')}")


def validate_rule(rule_id: int):
    """验证指定规则的过滤器配置"""
    print(f"验证规则 {rule_id} 的配置...")
    
    session = get_session()
    config_manager = get_filter_config_manager()
    
    try:
        rule = session.query(ForwardRule).filter_by(id=rule_id).first()
        if not rule:
            print(f"规则 {rule_id} 不存在")
            return False
        
        info = config_manager.get_rule_filter_info(rule)
        validation = info['validation']
        
        print(f"\n规则 {rule_id} 验证结果:")
        print(f"配置有效: {'是' if validation['valid'] else '否'}")
        
        if validation['errors']:
            print("\n错误:")
            for error in validation['errors']:
                print(f"  - {error}")
        
        if validation['warnings']:
            print("\n警告:")
            for warning in validation['warnings']:
                print(f"  - {warning}")
        
        if 'enabled_filters' in info:
            print(f"\n启用的过滤器 ({info['filter_count']} 个):")
            for i, filter_name in enumerate(info['enabled_filters'], 1):
                print(f"  {i:2d}. {filter_name}")
            
            if info['enabled_filters'] != info['optimized_order']:
                print(f"\n建议的优化顺序:")
                for i, filter_name in enumerate(info['optimized_order'], 1):
                    print(f"  {i:2d}. {filter_name}")
        
        return validation['valid']
        
    except Exception as e:
        print(f"验证失败: {str(e)}")
        return False
    finally:
        session.close()


def show_global_config():
    """显示全局配置"""
    print("全局过滤器配置:")
    
    config_manager = get_filter_config_manager()
    config = config_manager.get_global_config()
    
    print(f"\n禁用的过滤器:")
    disabled = config['disabled_filters']
    if disabled:
        for filter_name in disabled:
            print(f"  - {filter_name}")
    else:
        print("  (无)")
    
    print(f"\n缓存统计:")
    cache_stats = config['cache_stats']
    print(f"  缓存大小: {cache_stats['cache_size']}")
    print(f"  缓存键数: {len(cache_stats['cached_keys'])}")


def set_global_disabled(filters: list):
    """设置全局禁用的过滤器"""
    print(f"设置全局禁用过滤器: {filters}")
    
    config_manager = get_filter_config_manager()
    
    if config_manager.update_global_config(filters):
        print("设置成功")
        return True
    else:
        print("设置失败")
        return False


def export_rule_config(rule_id: int, output_file: str):
    """导出规则配置到文件"""
    print(f"导出规则 {rule_id} 的配置到 {output_file}")
    
    session = get_session()
    config_manager = get_filter_config_manager()
    
    try:
        rule = session.query(ForwardRule).filter_by(id=rule_id).first()
        if not rule:
            print(f"规则 {rule_id} 不存在")
            return False
        
        info = config_manager.get_rule_filter_info(rule)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        
        print("导出成功")
        return True
        
    except Exception as e:
        print(f"导出失败: {str(e)}")
        return False
    finally:
        session.close()


def import_rule_config(rule_id: int, input_file: str):
    """从文件导入规则配置"""
    print(f"从 {input_file} 导入配置到规则 {rule_id}")
    
    config_manager = get_filter_config_manager()
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 提取过滤器配置
        if 'validation' in config and 'config' in config['validation']:
            filter_config = config['validation']['config']
        elif 'filters' in config:
            filter_config = config
        else:
            print("无效的配置文件格式")
            return False
        
        if config_manager.update_rule_config(rule_id, filter_config):
            print("导入成功")
            return True
        else:
            print("导入失败")
            return False
            
    except Exception as e:
        print(f"导入失败: {str(e)}")
        return False


def clear_cache():
    """清空过滤器链缓存"""
    print("清空过滤器链缓存...")
    
    factory = get_filter_chain_factory()
    factory.clear_cache()
    
    print("缓存已清空")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='过滤器管理工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 迁移命令
    subparsers.add_parser('migrate', help='迁移现有规则到配置化过滤器链')
    
    # 列出过滤器命令
    subparsers.add_parser('list', help='列出所有可用的过滤器')
    
    # 验证规则命令
    validate_parser = subparsers.add_parser('validate', help='验证规则配置')
    validate_parser.add_argument('rule_id', type=int, help='规则ID')
    
    # 全局配置命令
    subparsers.add_parser('global', help='显示全局配置')
    
    # 设置全局禁用过滤器命令
    disable_parser = subparsers.add_parser('disable', help='设置全局禁用的过滤器')
    disable_parser.add_argument('filters', nargs='+', help='要禁用的过滤器名称')
    
    # 导出配置命令
    export_parser = subparsers.add_parser('export', help='导出规则配置')
    export_parser.add_argument('rule_id', type=int, help='规则ID')
    export_parser.add_argument('output', help='输出文件路径')
    
    # 导入配置命令
    import_parser = subparsers.add_parser('import', help='导入规则配置')
    import_parser.add_argument('rule_id', type=int, help='规则ID')
    import_parser.add_argument('input', help='输入文件路径')
    
    # 清除缓存命令
    subparsers.add_parser('clear-cache', help='清空过滤器链缓存')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    success = True
    
    try:
        if args.command == 'migrate':
            success = migrate_rules()
        elif args.command == 'list':
            list_filters()
        elif args.command == 'validate':
            success = validate_rule(args.rule_id)
        elif args.command == 'global':
            show_global_config()
        elif args.command == 'disable':
            success = set_global_disabled(args.filters)
        elif args.command == 'export':
            success = export_rule_config(args.rule_id, args.output)
        elif args.command == 'import':
            success = import_rule_config(args.rule_id, args.input)
        elif args.command == 'clear-cache':
            clear_cache()
        else:
            print(f"未知命令: {args.command}")
            success = False
    
    except KeyboardInterrupt:
        print("\n操作被用户中断")
        success = False
    except Exception as e:
        print(f"执行命令时发生错误: {str(e)}")
        logger.exception("详细错误信息:")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
