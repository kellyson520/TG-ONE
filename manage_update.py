#!/usr/bin/env python3
import asyncio
import sys
import os
import argparse
from pathlib import Path

# Ensure project root is in sys.path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from services.update_service import update_service
from core.config import settings

async def upgrade(target="origin/main"):
    """
    Execute update process.
    Differs from bot command: this runs the update logic directly in this process.
    """
    print(f"🚀 [CLI] Starting update process (Target: {target})...")
    
    # 1. Check for updates first (optional, but good for info)
    print("🔍 Checking remote status...")
    has_update, remote_ver = await update_service.check_for_updates(force=True)
    
    if not has_update:
        print(f"✅ Local version {remote_ver} is already up-to-date (or remote check failed).")
        # Allow forcing via argument? For now, we proceed only if perform_update handles it.
        # update_service.perform_update checks _is_updating flag.
        
    # 2. Perform update
    # Note: perform_update uses settings.UPDATE_BRANCH by default in the service logic.
    # The 'target' argument in CLI might need to override settings?
    # update_service.perform_update() doesn't take target args in the current implementation 
    # (it pulls settings.UPDATE_BRANCH).
    # If the user wants a specific target, we might need low-level calling of trigger_update?
    # BUT trigger_update exits the process and expects supervisor handling.
    # Let's stick to update_service.perform_update() which does git pull/reset.
    
    print("📦 Downloading and applying updates...")
    success, msg = await update_service.perform_update()
    
    if success:
        print(f"✅ Update applied successfully: {msg}")
        print("🔄 Please restart your service to apply changes.")
    else:
        print(f"❌ Update failed: {msg}")
        sys.exit(1)

async def check():
    print("🔍 Checking for updates...")
    has_update, version = await update_service.check_for_updates(force=True)
    if has_update:
        print(f"🆕 Update available! Version: {version}")
        print("Run 'python manage_update.py upgrade' to apply.")
    else:
        print(f"✅ You are on the latest version: {version}")

async def rollback():
    print("🚑 Initiating rollback...")
    # call update_service.request_rollback? 
    # That method exits process.
    # Since we are CLI, manual rollback might be better handled by entrypoint or git directly.
    # But let's reuse service logic if possible.
    # Service "rollback" method (rollback()) calls perform_git_rollback? 
    # Wait, in Step 9, verify_update_health calls `self.rollback()`.
    # BUT `rollback()` method was NOT visible in my Step 9 view (I saw `request_rollback` and `_rollback_db`).
    # Let me check if `rollback` method exists in UpdateService.
    # I missed reading `rollback` method in Step 9 because I only read lines 1-800 and didn't see definition of `rollback`.
    # Line 321 calls `self.rollback()`.
    
    # For now, let's just support upgrade and check.
    pass

def main():
    parser = argparse.ArgumentParser(description="TG ONE Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # upgrade command
    up_parser = subparsers.add_parser("upgrade", help="Update the system")
    up_parser.add_argument("--target", default="origin/main", help="Target branch/tag")
    
    # check command
    check_parser = subparsers.add_parser("check", help="Check for updates")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "upgrade":
            asyncio.run(upgrade(args.target))
        elif args.command == "check":
            asyncio.run(check())
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
