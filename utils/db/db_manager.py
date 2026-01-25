#!/usr/bin/env python3
"""
数据库管理工具 (异步调用版)
提供数据库维护、备份、优化等功能的命令行接口
"""
import argparse

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.models import backup_database  # 备份通常是文件操作，保持同步即可，或自行封装
from models.models import (
    async_analyze_database,
    async_cleanup_old_logs,
    async_get_database_info,
    async_get_db_health,
    async_vacuum_database,
)


# 辅助：运行异步函数的包装器
def run_async(coro):
    return asyncio.run(coro)


def cmd_backup(args):
    """备份数据库 (文件操作，保持同步)"""
    backup_path = backup_database(args.output)
    if backup_path:
        print(f"✅ 数据库备份成功: {backup_path}")
        return True
    else:
        print("❌ 数据库备份失败")
        return False


def cmd_vacuum(args):
    """清理数据库碎片 (异步)"""
    if run_async(async_vacuum_database()):
        print("✅ 数据库碎片清理完成")
        return True
    else:
        print("❌ 数据库碎片清理失败")
        return False


def cmd_analyze(args):
    """分析数据库 (异步)"""
    if run_async(async_analyze_database()):
        print("✅ 数据库统计信息分析完成")
        return True
    else:
        print("❌ 数据库分析失败")
        return False


def cmd_info(args):
    """显示数据库信息 (异步)"""
    info = run_async(async_get_database_info())
    if info:
        print("📊 数据库信息:")
        print(
            f"  数据库大小: {info['db_size']:,} 字节 ({info['db_size']/1024/1024:.2f} MB)"
        )
        print(
            f"  WAL 文件大小: {info['wal_size']:,} 字节 ({info['wal_size']/1024/1024:.2f} MB)"
        )
        print(
            f"  总大小: {info['total_size']:,} 字节 ({info['total_size']/1024/1024:.2f} MB)"
        )
        print(f"  表数量: {info['table_count']}")
        print(f"  索引数量: {info['index_count']}")
        return True
    else:
        print("❌ 获取数据库信息失败")
        return False


def cmd_health(args):
    """检查数据库健康状态 (异步)"""
    health = run_async(async_get_db_health())
    print(f"💊 数据库健康状态: {health['status']}")
    if health["status"] == "healthy":
        print("✅ 数据库运行正常")
        return True
    else:
        print(f"❌ 数据库异常: {health.get('error', '未知错误')}")
        return False


def cmd_cleanup(args):
    """清理旧日志 (异步)"""
    days = args.days
    deleted = run_async(async_cleanup_old_logs(days))
    print(f"✅ 清理完成: 删除了 {deleted} 条旧记录 (超过 {days} 天)")
    return True


def cmd_optimize(args):
    """优化数据库 (混合调用)"""
    print("🔧 开始数据库优化...")

    async def _optimize_steps():
        # 1. 分析统计信息
        print("  📊 分析统计信息...")
        if not await async_analyze_database():
            print("  ❌ 统计信息分析失败")
            return False

        # 2. 清理碎片
        if not args.skip_vacuum:
            print("  🧹 清理数据库碎片...")
            if not await async_vacuum_database():
                print("  ❌ 碎片清理失败")
                return False

        # 3. 清理旧日志
        if args.cleanup_days > 0:
            print(f"  🗑️ 清理 {args.cleanup_days} 天前的日志...")
            deleted = await async_cleanup_old_logs(args.cleanup_days)
            print(f"    删除了 {deleted} 条记录")

        return True

    if run_async(_optimize_steps()):
        print("✅ 数据库优化完成")
        return True
    else:
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 备份命令
    backup_parser = subparsers.add_parser("backup", help="备份数据库")
    backup_parser.add_argument("-o", "--output", help="备份文件路径")
    backup_parser.set_defaults(func=cmd_backup)

    # 清理碎片命令
    vacuum_parser = subparsers.add_parser("vacuum", help="清理数据库碎片")
    vacuum_parser.set_defaults(func=cmd_vacuum)

    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析数据库统计信息")
    analyze_parser.set_defaults(func=cmd_analyze)

    # 信息命令
    info_parser = subparsers.add_parser("info", help="显示数据库信息")
    info_parser.set_defaults(func=cmd_info)

    # 健康检查命令
    health_parser = subparsers.add_parser("health", help="检查数据库健康状态")
    health_parser.set_defaults(func=cmd_health)

    # 清理命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理旧日志")
    cleanup_parser.add_argument(
        "-d", "--days", type=int, default=30, help="清理多少天前的日志 (默认30天)"
    )
    cleanup_parser.set_defaults(func=cmd_cleanup)

    # 优化命令
    optimize_parser = subparsers.add_parser("optimize", help="优化数据库")
    optimize_parser.add_argument(
        "--skip-vacuum", action="store_true", help="跳过碎片清理"
    )
    optimize_parser.add_argument(
        "--cleanup-days", type=int, default=30, help="清理多少天前的日志 (0=跳过清理)"
    )
    optimize_parser.set_defaults(func=cmd_optimize)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        success = args.func(args)
        return 0 if success else 1
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        # import traceback; traceback.print_exc()
        return 1


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
