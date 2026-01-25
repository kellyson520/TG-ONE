import logging
import asyncio
import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)

class SystemService:
    """
    Service for system-wide configurations and state.
    """
    def __init__(self):
        self._allow_registration = True # Default
        
    def get_allow_registration(self) -> bool:
        return self._allow_registration
        
    def set_allow_registration(self, value: bool):
        self._allow_registration = value
        logger.info(f"Registration allowed set to: {value}")

    def get_logs(self, lines: int = 50, log_type: str = "app") -> str:
        """读取系统日志最近 N 行"""
        if log_type == "error":
            log_file = settings.LOG_DIR / "error.log"
        else:
            log_file = settings.LOG_DIR / "app.log"
            
        if not log_file.exists():
            return "Log file not found."
            
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            return f"Failed to read log: {e}"
    
    def get_log_file_path(self, log_type: str = "app") -> Optional[Path]:
        """获取日志文件路径 (用于下载)"""
        if log_type == "error":
            log_file = settings.LOG_DIR / "error.log"
        else:
            log_file = settings.LOG_DIR / "app.log"
        if log_file.exists():
            return log_file
        return None

    async def backup_database(self) -> Dict:
        """
        异步执行数据库备份
        """
        try:
            from utils.db.backup import backup_database as _backup
            
            # 在线程池中执行同步备份操作
            loop = asyncio.get_running_loop()
            backup_path = await loop.run_in_executor(None, _backup)
            
            if backup_path and os.path.exists(backup_path):
                size = os.path.getsize(backup_path) / (1024 * 1024)
                return {
                    "success": True, 
                    "path": backup_path, 
                    "size_mb": size
                }
            else:
                return {
                    "success": False, 
                    "error": "Backup function returned empty path"
                }
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                "success": False, 
                "error": str(e)
            }

    async def run_db_optimization(self, deep: bool = False) -> Dict[str, Any]:
        """运行数据库优化 (SQLite PRAGMA optimize/VACUUM)"""
        try:
            from models.models import AsyncSessionManager, cleanup_old_logs
            from sqlalchemy import text
            import time
            
            start_time = time.time()
            async with AsyncSessionManager() as session:
                if deep:
                    # Deep 模式：清理碎片
                    # 注意：VACUUM 不能在事务中运行，但在 SQLAlchemy 异步下需谨慎处理
                    # 这里我们使用同步引擎的方法作为参考，或者直接通过 session 执行
                    await session.execute(text("VACUUM;"))
                    logger.info("Database VACUUM completed.")
                else:
                    # Standard 模式：优化查询计划
                    await session.execute(text("PRAGMA optimize;"))
                
                # 无论哪种模式都更新统计信息
                await session.execute(text("ANALYZE;"))
                await session.commit()
            
            # 清理旧日志 (暂定 30 天)
            deleted_logs = 0
            if deep:
                from functools import partial
                import asyncio
                loop = asyncio.get_running_loop()
                deleted_logs = await loop.run_in_executor(None, partial(cleanup_old_logs, 30))
            
            return {
                "success": True,
                "duration": round(time.time() - start_time, 2),
                "deep": deep,
                "deleted_logs": deleted_logs,
                "message": f"Database optimization ({'VACUUM' if deep else 'PRAGMA optimize'} + ANALYZE) completed."
            }
        except Exception as e:
            logger.error(f"DB Optimization failed: {e}")
            return {"success": False, "error": str(e)}

class GuardService:
    """
    Guard service for hot-reloading and system health monitoring.
    """
    def __init__(self):
        self._stop_event = threading.Event()
        self._watch_thread = None
        self._config_task = None
        self._last_mtimes = {}
        self._watch_paths = [
            settings.BASE_DIR / ".env",
            settings.BASE_DIR / "main.py",
            settings.BASE_DIR / "core",
            settings.BASE_DIR / "services",
            settings.BASE_DIR / "web_admin"
        ]

    def start_guards(self):
        """启动所有守护任务"""
        logger.info("Initializing System Guards...")
        # 1. 启动文件监控 (逻辑热重载)
        if not self._watch_thread or not self._watch_thread.is_alive():
            self._stop_event.clear()
            self._watch_thread = threading.Thread(target=self._file_watcher_loop, daemon=True)
            self._watch_thread.start()
            logger.info("File watcher guard started.")



        # 2. 启动配置热加载 (定时从DB/Env同步)
        # 注意: config_task 需要在主 loop 中运行，由 main.py 调用 start_config_guard
        logger.info("Guard service initial setup complete.")
        
    async def start_guards_async(self):
        """启动异步守护任务"""
        await asyncio.gather(
            self.start_config_guard(),
            self.start_memory_guard(),
            self.start_db_health_guard(),
        )

    def stop_guards(self):
        """同步停止所有守护逻辑信号"""
        logger.info("Stopping System Guards...")
        self._stop_event.set()
        logger.info("System Guards stop signal sent.")

    async def start_config_guard(self):
        """异步配置同步守护任务"""
        logger.info("Starting config hot-load guard...")
        while not self._stop_event.is_set():
            try:
                # 每 60 秒同步一次动态配置
                await asyncio.sleep(60)
                await settings.load_dynamic_config()
                # logger.debug("Dynamic configuration synchronized from database.")
            except Exception as e:
                logger.error(f"Error in config hot-load guard: {e}")

    async def start_memory_guard(self):
        """异步内存维护任务"""
        logger.info("Starting memory maintenance guard...")
        import gc
        while not self._stop_event.is_set():
            try:
                # 每 30 分钟执行一次
                await asyncio.sleep(1800)
                # 强制回收
                unreachable = gc.collect()
                if unreachable > 0:
                    logger.info(f"Memory Guard: GC collected {unreachable} objects")
            except Exception as e:
                logger.error(f"Error in memory guard: {e}")

    async def start_db_health_guard(self):
        """异步数据库健康检查 (Reporting Only)"""
        logger.info("Starting DB health monitor...")
        from utils.db.health_check import DatabaseHealthManager, settings as db_settings
        
        # 只在启用时运行
        if not db_settings.ENABLE_DB_HEALTH_CHECK:
            return

        while not self._stop_event.is_set():
            try:
                # 每 4 小时检查一次
                await asyncio.sleep(4 * 3600)
                
                # Check DBs
                db_url = db_settings.DATABASE_URL
                if db_url.startswith("sqlite"):
                    path_str = db_url.split("///")[-1]
                    db_path = Path(db_settings.BASE_DIR) / path_str
                    
                    manager = DatabaseHealthManager(str(db_path))
                    # Runtime check only, no repair (unsafe while running)
                    is_healthy = manager.check_health()
                    
                    if not is_healthy:
                        logger.critical("RUNTIME DB CORRUPTION DETECTED! Please restart service to trigger auto-repair.")
                        # TODO: Maybe send alert via Bot
                        
            except Exception as e:
                logger.error(f"Error in DB health guard: {e}")

    def _file_watcher_loop(self):
        """文件变化监控循环 (阻塞式线程)"""
        # 初始化记录
        self._update_mtimes()
        
        while not self._stop_event.is_set():
            try:
                changed = self._check_changes()
                if changed:
                    logger.info(f"Detected change in: {changed}. Triggering hot-restart...")
                    # 给 1 秒缓冲，避免频繁重启或写入未完成
                    time.sleep(1)
                    self._restart_process()
                
                time.sleep(2) # 每 2 秒检查一次
            except Exception as e:
                logger.error(f"Error in file watcher: {e}")
                time.sleep(5)

    def _update_mtimes(self):
        """更新所有监控路径的修改时间"""
        for path in self._watch_paths:
            if not path.exists():
                continue
            if path.is_file():
                self._last_mtimes[str(path)] = path.stat().st_mtime
            else:
                for p in path.glob("**/*.py"):
                    self._last_mtimes[str(p)] = p.stat().st_mtime

    def _check_changes(self) -> Optional[str]:
        """检查是否有文件发生变化"""
        for path in self._watch_paths:
            if not path.exists():
                continue
            
            if path.is_file():
                mtime = path.stat().st_mtime
                if str(path) not in self._last_mtimes or mtime > self._last_mtimes[str(path)]:
                    self._last_mtimes[str(path)] = mtime
                    return str(path)
            else:
                # 递归检查子目录中的 .py 文件
                for p in path.glob("**/*.py"):
                    mtime = p.stat().st_mtime
                    if str(p) not in self._last_mtimes or mtime > self._last_mtimes[str(p)]:
                        self._last_mtimes[str(p)] = mtime
                        return str(p)
        return None

    def trigger_restart(self):
        """人工触发重启"""
        self._restart_process()

    def _restart_process(self):
        """
        重启当前进程 (优雅版本)
        """
        logger.info("触发优雅重启流程...")
        
        try:
            # 导入优雅关闭协调器
            from core.shutdown import get_shutdown_coordinator
            coordinator = get_shutdown_coordinator()
            
            # 获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            
            # 在事件循环中触发优雅关闭
            async def _graceful_restart():
                logger.info("执行优雅关闭...")
                success = await coordinator.shutdown()
                
                if success:
                    logger.info("✓ 优雅关闭成功，进程即将退出")
                else:
                    logger.warning("✗ 优雅关闭部分失败，强制退出")
                
                sys.exit(0)
            
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(_graceful_restart())
            )
            
            logger.info("优雅重启信号已发送")
            
        except Exception as e:
            logger.error(f"触发优雅重启失败: {e}")
            logger.warning("降级为直接退出")
            sys.exit(1)


system_service = SystemService()
guard_service = GuardService()
