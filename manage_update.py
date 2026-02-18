import asyncio
import sys
import os
import argparse
import json
from pathlib import Path

# 添加项目根目录到路径 (Moved to root, so current dir is root)
sys.path.append(str(Path(__file__).parent))

from core.config import settings
from services.update_service import update_service
from version import VERSION, get_latest_changelog

async def show_status():
    """显示当前更新状态"""
    print("🔍 [Update Manager] 正在检查系统状态...")
    
    # 尝试 Git 检查
    has_update, remote_ver = await update_service.check_for_updates(force=True)
    
    # 获取历史记录
    history = await update_service.get_update_history(limit=5)
    
    print(f"\n--- 系统版本信息 ---")
    print(f"核心版本: v{VERSION}")
    if history:
        current = history[0]
        status_label = "HEAD" if update_service._is_git_repo else "Standard"
        print(f"Git 版本 ({status_label}): {current['short_sha']} ({current['timestamp']})")
        print(f"最新描述: {current['message']}")
    else:
        print("Git 状态: 未接入")
        
    print(f"\n--- 最近更新日志 ---")
    print(get_latest_changelog())
        
    print(f"\n--- 更新检查 ---")
    if has_update:
        print(f"🆕 发现新版本: {remote_ver}")
        print(f"执行建议: 使用 `python manage_update.py upgrade` 进行更新")
    else:
        print("✅ 当前已是最新版本 (或者无法连接远程获取更新状态)")
        
    # 查看是否有锁文件
    lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
    verify_lock = settings.BASE_DIR / "data" / "UPDATE_VERIFYING.json"
    
    if lock_file.exists():
        print(f"\n⚠️ 警告: 发现更新锁文件 (系统可能正在更新中或上次更新未完成)")
    if verify_lock.exists():
        print(f"\n🛡️ 提示: 系统当前处于更新后的“稳定性观察期”")

async def upgrade(target=None):
    """触发升级"""
    target = target or settings.UPDATE_BRANCH
    print(f"🚀 [Update Manager] 准备将系统升级至: {target}")
    
    confirm = input("确定要继续吗？(y/N): ")
    if confirm.lower() != 'y':
        print("已取消。")
        return
        
    try:
        # 复用 UpdateService 的逻辑
        await update_service.trigger_update(target_version=target)
    except SystemExit:
        print("✅ 更新指令已发出，系统将立即退出并由守护进程接管流程。")
        sys.exit(0) # 命令行工具正常退出，如果是 Bot 调用则由 Bot 处理退出
    except Exception as e:
        print(f"❌ 触发更新失败: {e}")

async def rollback():
    """手动触发回退"""
    print(f"⏪ [Update Manager] 准备执行系统回滚...")
    
    confirm = input("警告：回退将尝试执行 `git reset --hard` (Git 模式) 或还原物理备份 (非 Git 模式)。确定继续？(y/N): ")
    if confirm.lower() != 'y':
        print("已取消。")
        return

    # 这里我们复用 UpdateService 的 trigger_update 逻辑，但通过标志位告诉 entrypoint.sh 我们要的是回滚
    # 复用 UpdateService 的 request_rollback 方法
    
    try:
        # 复用 UpdateService 的逻辑
        await update_service.request_rollback()
    except SystemExit:
        print("✅ 回滚请求已发出，系统将立即退出并由守护进程执行回滚流程。")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 触发回退失败: {e}")

async def list_backups():
    """列出所有本地代码备份"""
    print("📦 [Update Manager] 正在检索本地备份...")
    # 动态导入防止循环依赖
    from services.update_service import update_service
    backups = await update_service.list_local_backups()
    
    if not backups:
        print("📭 未发现任何本地备份。")
        return
        
    print("\n--- 可用的本地备份 (最近 10 个) ---")
    print(f"{'编号':<4} {'备份日期':<22} {'大小':<10} {'含DB':<6} {'文件名'}")
    for i, b in enumerate(backups, 1):
        db_flag = "✅" if b.get('has_db') else "❌"
        size_str = f"{b.get('size_mb', 0):.1f}MB"
        print(f"{i:<6} {b['timestamp']:<22} {size_str:<10} {db_flag:<6} {b['name']}")
        
    print("\n提示: 使用 `python manage_update.py restore <编号>` 进行指定还原")

async def restore_specific(index: int):
    """还原指定的本地备份"""
    # 动态导入防止循环依赖
    from services.update_service import update_service
    backups = await update_service.list_local_backups()
    if not backups or index < 1 or index > len(backups):
        print(f"❌ 错误: 无效的备份编号 {index}")
        return
        
    target = backups[index-1]
    print(f"⏪ [Update Manager] 准备还原备份: {target['name']}")
    confirm = input(f"警告：这将覆盖当前代码！确定还原日期为 {target['timestamp']} 的备份吗？(y/N): ")
    if confirm.lower() != 'y':
        print("已取消。")
        return
        
    success, msg = await update_service.restore_from_backup(target['path'])
    if success:
        print(f"✅ 还原成功: {msg}")
        print("请手动重启应用。")
    else:
        print(f"❌ 还原失败: {msg}")

def main():
    parser = argparse.ArgumentParser(description="TG ONE 更新与回滚管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # status
    subparsers.add_parser("status", help="查看当前系统版本与更新状态")
    
    # upgrade
    up_parser = subparsers.add_parser("upgrade", help="手动触发升级")
    up_parser.add_argument("target", nargs="?", help="目标分支、SHA 或 Tag (默认使用配置中的分支)")
    
    # rollback
    subparsers.add_parser("rollback", help="自动回滚至上个稳定版本")
    
    # list-backups
    subparsers.add_parser("list-backups", help="列出所有可用的本地代码备份")
    
    # restore
    restore_parser = subparsers.add_parser("restore", help="从指定备份还原代码")
    restore_parser.add_argument("index", type=int, help="备份编号 (见 list-backups)")
    
    args = parser.parse_args()
    
    if args.command == "status":
        asyncio.run(show_status())
    elif args.command == "upgrade":
        asyncio.run(upgrade(args.target))
    elif args.command == "rollback":
        asyncio.run(rollback())
    elif args.command == "list-backups":
        asyncio.run(list_backups())
    elif args.command == "restore":
        asyncio.run(restore_specific(args.index))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
