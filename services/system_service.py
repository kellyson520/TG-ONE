import logging
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
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
            from repositories.backup import backup_database as _backup
            
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
    Fully asynchronous implementation.
    """
    def __init__(self):
        self._stop_event = asyncio.Event()
        self._last_mtimes = {}
        self._watch_paths = [
            settings.BASE_DIR / ".env",
            settings.BASE_DIR / "main.py",
            settings.BASE_DIR / "core",
            settings.BASE_DIR / "services",
            settings.BASE_DIR / "web_admin"
        ]
        # Maintenance settings
        self._temp_guard_max = settings.TEMP_GUARD_MAX
        self._temp_guard_path = settings.TEMP_DIR
        self._memory_limit_mb = 500 # Default limit

    def start_guards(self):
        """Deprecated: Use start_guards_async instead."""
        pass
        
    async def start_guards_async(self):
        """启动所有异步守护任务"""
        logger.info("🚀 Initializing All System Guards (Async)...")
        self._stop_event.clear()
        
        # 记录初始文件时间
        self._update_mtimes()
        
        # 使用 exception_handler 或者 gather 启动所有背景任务
        # 我们这里让它们作为长驻任务运行
        tasks = [
            self.start_config_guard(),
            self.start_memory_guard(),
            self.start_db_health_guard(),
            self.start_temp_guard(),
            self.start_file_watcher_guard()
        ]
        
        # 启动背景任务
        for task in tasks:
            asyncio.create_task(task)
            
        logger.info("✅ All Guards initiated.")

    def stop_guards(self):
        """停止所有守护逻辑信号"""
        logger.info("Stopping System Guards...")
        self._stop_event.set()

    async def start_config_guard(self):
        """异步配置同步守护任务"""
        logger.info("[guard] Config hot-load guard initiated.")
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(60)
                from core.config_initializer import load_dynamic_config_from_db
                await load_dynamic_config_from_db(settings)
            except Exception as e:
                logger.error(f"[guard-config] Error: {e}")

    async def start_memory_guard(self):
        """异步内存及墓碑化维护任务"""
        logger.info("[guard] Memory guard initiated (Limit: {}MB).".format(self._memory_limit_mb))
        import gc
        import psutil
        from core.helpers.tombstone import tombstone
        
        check_interval = 30
        gc_interval = 1800
        last_gc = time.time()
        
        while not self._stop_event.is_set():
            try:
                now = time.time()
                # 1. 定时 GC
                if now - last_gc > gc_interval:
                    unreachable = gc.collect()
                    if unreachable > 0:
                        logger.debug(f"[guard-mem] GC collected {unreachable} objects")
                    last_gc = now
                
                # 2. 内存阈值检查
                try:
                    process = psutil.Process()
                    rss_mb = process.memory_info().rss / 1024 / 1024
                    
                    if rss_mb > self._memory_limit_mb and not tombstone._is_frozen:
                        logger.warning(f"[guard-mem] Memory threshold exceeded ({rss_mb:.2f}MB > {self._memory_limit_mb}MB)")
                        await tombstone.freeze()
                    elif rss_mb < (self._memory_limit_mb * 0.7) and tombstone._is_frozen:
                        # 内存降下来后尝试复苏
                        await tombstone.resurrect()
                except Exception as e:
                    logger.error(f"[guard-mem] Memory check error: {e}")
                
                await asyncio.sleep(check_interval)
            except Exception as e:
                logger.error(f"[guard-mem] Error: {e}")
                await asyncio.sleep(60)

    async def start_temp_guard(self):
        """异步临时文件清理守护任务"""
        logger.info("[guard] Temp directory guard initiated (Limit: {}GB).".format(self._temp_guard_max // 1024**3))
        while not self._stop_event.is_set():
            try:
                if self._temp_guard_path.exists():
                    files = []
                    total_size = 0
                    for f in self._temp_guard_path.rglob('*'):
                        if f.is_file():
                            try:
                                stat = f.stat()
                                total_size += stat.st_size
                                files.append((stat.st_mtime, stat.st_size, f))
                            except OSError:
                                pass
                    
                    if total_size > self._temp_guard_max:
                        # 按时间升序排序（最旧的在前）
                        files.sort(key=lambda x: x[0])
                        deleted_size = 0
                        target_size = total_size - self._temp_guard_max
                        deleted_count = 0
                        
                        for _, size, f in files:
                            if deleted_size >= target_size:
                                break
                            try:
                                if f.exists():
                                    f.unlink()
                                    deleted_size += size
                                    deleted_count += 1
                            except Exception:
                                pass
                        
                        if deleted_count > 0:
                            logger.info(f"[guard-temp] Cleaned {deleted_count} files, freed {deleted_size/1024/1024:.2f}MB")
                
                await asyncio.sleep(3600) # 每小时检查
            except Exception as e:
                logger.error(f"[guard-temp] Error: {e}")
                await asyncio.sleep(3600)

    async def start_db_health_guard(self):
        """异步数据库健康检查"""
        logger.info("[guard] DB health monitor initiated.")
        from repositories.health_check import DatabaseHealthManager, settings as db_settings
        if not db_settings.ENABLE_DB_HEALTH_CHECK:
            return

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(4 * 3600)
                db_url = db_settings.DATABASE_URL
                if db_url.startswith("sqlite"):
                    path_str = db_url.split("///")[-1]
                    db_path = Path(db_settings.BASE_DIR) / path_str
                    manager = DatabaseHealthManager(str(db_path))
                    if not manager.check_health():
                        logger.critical("[guard-db] RUNTIME DB CORRUPTION DETECTED!")
            except Exception as e:
                logger.error(f"[guard-db] Error: {e}")

    async def start_file_watcher_guard(self):
        """异步文件变化监控 (热重启)"""
        logger.info("[guard] File watcher guard initiated.")
        while not self._stop_event.is_set():
            try:
                changed = await asyncio.to_thread(self._check_changes)
                if changed:
                    logger.info(f"[guard-watcher] Detected change: {changed}. Triggering hot-restart...")
                    await asyncio.sleep(1)
                    await self._restart_process_async()
                await asyncio.sleep(5) # 每5秒检查一次
            except Exception as e:
                logger.error(f"[guard-watcher] Error: {e}")
                await asyncio.sleep(10)

    def _update_mtimes(self):
        for path in self._watch_paths:
            if not path.exists(): continue
            if path.is_file():
                self._last_mtimes[str(path)] = path.stat().st_mtime
            else:
                for p in path.glob("**/*.py"):
                    self._last_mtimes[str(p)] = p.stat().st_mtime

    def _check_changes(self) -> Optional[str]:
        for path in self._watch_paths:
            if not path.exists(): continue
            if path.is_file():
                mtime = path.stat().st_mtime
                if str(path) not in self._last_mtimes or mtime > self._last_mtimes[str(path)]:
                    self._last_mtimes[str(path)] = mtime
                    return str(path)
            else:
                for p in path.glob("**/*.py"):
                    mtime = p.stat().st_mtime
                    if str(p) not in self._last_mtimes or mtime > self._last_mtimes[str(p)]:
                        self._last_mtimes[str(p)] = mtime
                        return str(p)
        return None

    async def _restart_process_async(self):
        """异步触发重启"""
        logger.info("Triggering graceful restart...")
        from core.shutdown import get_shutdown_coordinator
        coordinator = get_shutdown_coordinator()
        try:
            await coordinator.shutdown()
            sys.exit(0)
        except Exception as e:
            logger.error(f"Graceful restart failed: {e}")
            sys.exit(1)

    def trigger_restart(self):
        asyncio.create_task(self._restart_process_async())


system_service = SystemService()
guard_service = GuardService()
