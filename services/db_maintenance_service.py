import logging
import os
import shutil
import sqlite3
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Chat, ForwardRule
from services.network.api_optimization import get_api_optimizer
from core.helpers.entity_validator import get_entity_validator

from core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库权限与备份管理器"""

    def __init__(self):
        self.project_root = settings.BASE_DIR
        self.session_dir = settings.SESSION_DIR
        self.db_dir = settings.DB_DIR
        self.backup_dir = settings.BACKUP_DIR

    def check_directory_permissions(self, directory: Path) -> Dict[str, bool]:
        """检查目录权限"""
        result = {"exists": False, "readable": False, "writable": False, "executable": False}
        try:
            if directory.exists():
                result["exists"] = True
                result["readable"] = os.access(directory, os.R_OK)
                result["writable"] = os.access(directory, os.W_OK)
                result["executable"] = os.access(directory, os.X_OK)
        except Exception as e:
            logger.error(f"检查目录权限失败 {directory}: {e}")
        return result

    def check_file_permissions(self, file_path: Path) -> Dict[str, bool]:
        """检查文件权限"""
        result = {"exists": False, "readable": False, "writable": False, "size": 0, "locked": False}
        try:
            if file_path.exists():
                result["exists"] = True
                result["readable"] = os.access(file_path, os.R_OK)
                result["writable"] = os.access(file_path, os.W_OK)
                result["size"] = file_path.stat().st_size
                try:
                    with open(file_path, "a"):
                        pass
                except (PermissionError, IOError):
                    result["locked"] = True
        except Exception as e:
            logger.error(f"检查文件权限失败 {file_path}: {e}")
        return result

    def fix_directory_permissions(self, directory: Path) -> bool:
        """修复目录权限"""
        try:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建目录: {directory}")

            if os.name == "nt":  # Windows
                try:
                    import subprocess
                    subprocess.run(
                        ["icacls", str(directory), "/grant", f'{settings.OS_USERNAME}:F', "/t"],
                        capture_output=True, check=False
                    )
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            else:
                directory.chmod(0o755)
            return True
        except Exception as e:
            logger.error(f"修复目录权限失败 {directory}: {e}")
            return False

    def fix_file_permissions(self, file_path: Path) -> bool:
        """修复文件权限"""
        try:
            if not file_path.exists():
                file_path.touch()
            
            if os.name == "nt":
                try:
                    import subprocess
                    subprocess.run(
                        ["icacls", str(file_path), "/grant", f'{settings.OS_USERNAME}:F', "/t"],
                        capture_output=True, check=False
                    )
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            else:
                file_path.chmod(0o644)
            return True
        except Exception as e:
            logger.error(f"修复文件权限失败 {file_path}: {e}")
            return False

    def test_database_write(self, db_path: Path) -> bool:
        """测试数据库是否可写"""
        try:
            if not db_path.exists():
                db_path.touch()
            with sqlite3.connect(str(db_path), timeout=10.0) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS test_write (id INTEGER)")
                conn.execute("INSERT OR REPLACE INTO test_write (id) VALUES (1)")
                conn.commit()
                conn.execute("DROP TABLE IF EXISTS test_write")
                conn.commit()
            return True
        except Exception as e:
            # Use warning instead of error for write tests (common for locked files)
            logger.warning(f"数据库写入测试失败 {db_path}: {e}")
            return False

    def backup_database(self, db_path: Path) -> Optional[Path]:
        """备份数据库"""
        try:
            if not db_path.exists():
                return None
            timestamp = int(time.time())
            if not self.backup_dir.exists():
                self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_dir / f"{db_path.stem}.backup.{timestamp}{db_path.suffix}"
            shutil.copy2(db_path, backup_path)
            return backup_path
        except Exception as e:
            logger.error(f"数据库备份失败 {db_path}: {e}")
            return None

    def scan_database_files(self) -> List[Path]:
        """扫描所有数据库文件 (排除备份)"""
        db_files = []
        search_patterns = ["*.db", "*.sqlite", "*.sqlite3", "*.session"]
        for directory in [self.session_dir, self.db_dir]:
            if directory.exists():
                for pattern in search_patterns:
                    # Scan current dir
                    files = list(directory.glob(pattern))
                    # Scan subdirs recursively
                    files.extend(directory.glob(f"**/{pattern}"))
                    
                    for f in files:
                        # Exclude backup directories and files
                        if "backup" in str(f).lower() or ".backup." in f.name:
                            continue
                        db_files.append(f)
                        
        return sorted(list(set(db_files)))

    def fix_all_permissions(self) -> Tuple[int, int]:
        """修复所有数据库相关的权限问题"""
        success_count = 0
        total_count = 0
        
        for directory in [self.session_dir, self.db_dir]:
            total_count += 1
            if self.fix_directory_permissions(directory):
                success_count += 1

        db_files = self.scan_database_files()
        for db_path in db_files:
            total_count += 1
            if self.test_database_write(db_path):
                success_count += 1
            else:
                if self.fix_file_permissions(db_path) and self.test_database_write(db_path):
                    success_count += 1
        return success_count, total_count

class DatabaseCleaner:
    """数据库内容清理器"""

    def __init__(self):
        self.validator = get_entity_validator()

    async def scan_and_mark_invalid_chats(self, session: AsyncSession, limit: int = 100) -> Dict[str, Any]:
        """扫描并标记无效的聊天记录"""
        stmt = select(Chat).where(Chat.is_active == True).limit(limit)
        result = await session.execute(stmt)
        chats = result.scalars().all()
        results = {"total_scanned": len(chats), "marked_inactive": 0}

        api_optimizer = get_api_optimizer()
        if not api_optimizer:
            return results

        for chat in chats:
            if not self.validator.is_likely_valid_chat_id(chat.telegram_chat_id):
                chat.is_active = False
                results["marked_inactive"] += 1
        
        await session.commit()
        return results

    async def cleanup_orphaned_rules(self, session: AsyncSession) -> Dict[str, Any]:
        """清理孤立的转发规则"""
        from sqlalchemy.orm import joinedload
        # 预加载 source_chat 和 target_chat
        stmt = (
            select(ForwardRule)
            .options(joinedload(ForwardRule.source_chat), joinedload(ForwardRule.target_chat))
            .where(ForwardRule.enable_rule == True)
        )
        result = await session.execute(stmt)
        rules = result.scalars().all()
        results = {"total_rules": len(rules), "disabled_rules": 0}

        for rule in rules:
            # 现在直接访问 rule.source_chat 不会触发查询
            source_active = rule.source_chat.is_active if rule.source_chat else False
            target_active = rule.target_chat.is_active if rule.target_chat else False
            
            if not source_active or not target_active:
                rule.enable_rule = False
                results["disabled_rules"] += 1

        await session.commit()
        return results

    async def full_cleanup(self, session: AsyncSession, chat_scan_limit: int = 50) -> Dict[str, Any]:
        """执行完整清理"""
        chat_results = await self.scan_and_mark_invalid_chats(session, chat_scan_limit)
        rule_results = await self.cleanup_orphaned_rules(session)
        return {
            "chat_cleanup": chat_results,
            "rule_cleanup": rule_results,
            "status": "completed"
        }

class DBMaintenanceService:
    """统一数据库维护服务"""
    
    def __init__(self):
        self.manager = DatabaseManager()
        self.cleaner = DatabaseCleaner()

    async def run_maintenance(self, session: Optional[AsyncSession] = None):
        """运行定期维护流程"""
        logger.info("Starting scheduled DB maintenance...")
        # 1. 修复权限 (同步执行)
        await asyncio.to_thread(self.manager.fix_all_permissions)
        # 2. 清理数据 (如果提供了 session)
        if session:
            await self.cleaner.full_cleanup(session)
        
        # 3. 自动归档冷数据 (热冷分层)
        if settings.AUTO_ARCHIVE_ENABLED:
            try:
                await self.auto_archive_data()
            except Exception as e:
                logger.error(f"Auto-archive failed during maintenance: {e}")
                
        logger.info("DB maintenance complete.")

    async def auto_archive_data(self) -> Dict[str, Any]:
        """按配置执行全量归档任务"""
        logger.info("🚀 [DBMaintenance] 开始执行自动归档任务...")
        from core.container import container
        
        results = {}
        
        # 1. 归档任务队列 (TaskQueue)
        try:
            results["task_queue"] = await container.task_repo.archive_old_tasks(
                hot_days=settings.HOT_DAYS_TASK,
                batch_size=settings.ARCHIVE_BATCH_SIZE
            )
        except Exception as e:
            logger.error(f"TaskQueue archive failed: {e}")
            results["task_queue"] = {"error": str(e)}

        # 2. 归档转发日志 (RuleLog/Statistics)
        try:
            results["stats"] = await container.stats_repo.archive_old_logs(
                hot_days_log=settings.HOT_DAYS_LOG,
                hot_days_stats=settings.HOT_DAYS_STATS
            )
        except Exception as e:
            logger.error(f"Stats archive failed: {e}")
            results["stats"] = {"error": str(e)}

        # 3. 归档审计日志 (AuditLog)
        try:
            results["audit"] = await container.audit_repo.archive_old_audit_logs(
                hot_days=settings.HOT_DAYS_LOG
            )
        except Exception as e:
            logger.error(f"Audit archive failed: {e}")
            results["audit"] = {"error": str(e)}

        # 4. 归档去重指纹 (MediaSignature)
        try:
            # 去重指纹通常保留时间较长，默认 60 天
            results["dedup"] = await container.dedup_repo.archive_old_signatures(
                hot_days=settings.HOT_DAYS_SIGN
            )
        except Exception as e:
            logger.error(f"Dedup archive failed: {e}")
            results["dedup"] = {"error": str(e)}

        logger.info("✅ [DBMaintenance] 自动归档任务完成")
        return results

    async def optimize_database(self) -> Dict[str, Any]:
        """优化数据库性能 (ANALYZE + VACUUM)"""
        try:
            from models.models import analyze_database, vacuum_database
            await asyncio.to_thread(analyze_database)
            await asyncio.to_thread(vacuum_database)
            return {"success": True, "message": "数据库已优化 (ANALYZE & VACUUM 完成)"}
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_database_info(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            from core.config import settings
            db_path = Path(settings.DB_PATH.replace("sqlite+aiosqlite:///", ""))
            info = self.manager.check_file_permissions(db_path)
            
            # 简单的统计
            from core.container import container
            from sqlalchemy import func
            from models.models import ErrorLog, RuleLog, Chat, ForwardRule
            
            tables = {}
            async with container.db.get_session() as session:
                for model in [Chat, ForwardRule, ErrorLog, RuleLog]:
                    stmt = select(func.count()).select_from(model)
                    count = (await session.execute(stmt)).scalar() or 0
                    tables[model.__tablename__] = count
            
            return {
                "success": True,
                "size_mb": info["size"] / (1024 * 1024),
                "total_rows": sum(tables.values()),
                "tables": tables
            }
        except Exception as e:
            logger.error(f"获取组件信息失败: {e}")
            return {"success": False, "error": str(e)}

    async def backup_database(self) -> Dict[str, Any]:
        """执行数据库备份"""
        try:
            from core.config import settings
            db_path = Path(settings.DB_PATH.replace("sqlite+aiosqlite:///", ""))
            backup_path = await asyncio.to_thread(self.manager.backup_database, db_path)
            if backup_path:
                return {
                    "success": True, 
                    "path": str(backup_path),
                    "size_mb": backup_path.stat().st_size / (1024 * 1024)
                }
            return {"success": False, "error": "备份失败"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_integrity(self) -> Dict[str, Any]:
        """检查数据库完整性"""
        try:
            from core.container import container
            from sqlalchemy import text
            async with container.db.get_session() as session:
                result = await session.execute(text("PRAGMA integrity_check"))
                status = result.scalar()
            return {
                "success": True,
                "integrity_check": status,
                "fragmentation": 0 # Placeholder if not easy to get
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# 全局服务实例
db_maintenance_service = DBMaintenanceService()
