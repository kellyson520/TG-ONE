import asyncio
import sys
import os
import argparse
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.config import settings
from services.update_service import update_service

async def show_status():
    """显示当前更新状态"""
    print("🔍 [Update Manager] 正在检查系统状态...")
    
    # 尝试 Git 检查
    has_update, remote_ver = await update_service.check_for_updates(force=True)
    
    # 获取历史记录
    history = await update_service.get_update_history(limit=5)
    
    print(f"\n--- 系统版本信息 ---")
    if history:
        current = history[0]
        print(f"当前版本 (HEAD): {current['short_sha']} ({current['timestamp']})")
        print(f"描述: {current['message']}")
        print(f"作者: {current['author']}")
    else:
        print("当前版本: 未知 (非 Git 仓库)")
        
    print(f"\n--- 更新检查 ---")
    if has_update:
        print(f"🆕 发现新版本: {remote_ver}")
        print(f"执行建议: 使用 `python manage_update.py upgrade` 进行更新")
    else:
        print("✅ 当前已是最新版本 (或者无法通过 Git 连接远程仓库)")
        
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
    
    confirm = input("警告：回滚将尝试执行 `git reset --hard` 到上一个记录的版本，或者还原物理备份。确定继续？(y/N): ")
    if confirm.lower() != 'y':
        print("已取消。")
        return

    # 这里我们复用 UpdateService 的 trigger_update 逻辑，但通过标志位告诉 entrypoint.sh 我们要的是回滚
    lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
    
    # 获取当前版本作为 "故障版本" 记录（虽然没啥大用，但为了逻辑一致）
    # 关键是我们需要一个状态让守护进程知道启动即回滚
    # 我们可以通过 trigger_update 并设置一个特殊的 target，或者直接操作锁文件
    
    try:
        # 复用 UpdateService 的逻辑
        await update_service.request_rollback()
    except SystemExit:
        print("✅ 回滚请求已发出，系统将立即退出并由守护进程执行回滚流程。")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 触发回滚失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="TG ONE 更新与回滚管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # status
    subparsers.add_parser("status", help="查看当前系统版本与更新状态")
    
    # upgrade
    up_parser = subparsers.add_parser("upgrade", help="手动触发升级")
    up_parser.add_argument("target", nargs="?", help="目标分支、SHA 或 Tag (默认使用配置中的分支)")
    
    # rollback
    subparsers.add_parser("rollback", help="手动触发回滚")
    
    args = parser.parse_args()
    
    if args.command == "status":
        asyncio.run(show_status())
    elif args.command == "upgrade":
        asyncio.run(upgrade(args.target))
    elif args.command == "rollback":
        asyncio.run(rollback())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
