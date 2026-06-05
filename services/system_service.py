import logging
import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)

class SystemService:
    """
    Service for system-wide configurations and state.
    """
    def __init__(self):
        pass # Settings managed via core.config.settings and config_service
        
    @property
    def container(self):
        from core.container import container
        return container

    async def is_maintenance_mode(self) -> bool:
        """检查系统是否处于维护模式"""
        try:
            from models.system import SystemConfiguration
            from sqlalchemy import select
            
            async with self.container.db.get_session() as s:
                result = await s.execute(select(SystemConfiguration).filter_by(key="maintenance_mode"))
                config = result.scalar_one_or_none()
                return config and config.value.lower() == "true"
        except Exception as e:
            logger.error(f"Failed to check maintenance mode: {e}")
            return False

    async def set_maintenance_mode(self, enabled: bool) -> bool:
        """设置系统维护模式"""
        try:
            from models.system import SystemConfiguration
            from sqlalchemy import select
            
            async with self.container.db.get_session() as s:
                result = await s.execute(select(SystemConfiguration).filter_by(key="maintenance_mode"))
                config = result.scalar_one_or_none()
                
                value = "true" if enabled else "false"
                if config:
                    config.value = value
                else:
                    config = SystemConfiguration(key="maintenance_mode", value=value)
                    s.add(config)
                
                await s.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set maintenance mode: {e}")
            return False
        
    def get_allow_registration(self) -> bool:
        return settings.ALLOW_REGISTRATION
        
    async def set_allow_registration(self, value: bool):
        from services.config_service import config_service
        # 持久化到数据库
        await config_service.set("ALLOW_REGISTRATION", value, data_type="boolean")
        # 同步更新内存中的 settings 对象，确保后续请求立即生效
        settings.ALLOW_REGISTRATION = value
        logger.info(f"Registration allowed set to: {value}")

    async def get_system_configurations(self, limit: int = 20):
        """获取系统配置列表"""
        try:
            from models.system import SystemConfiguration
            from sqlalchemy import select
            async with self.container.db.get_session() as s:
                result = await s.execute(select(SystemConfiguration).limit(limit))
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get system configurations: {e}")
            return []

    async def get_error_logs(self, limit: int = 5):
        """获取最近的消息错误日志"""
        try:
            from models.system import ErrorLog  # ErrorLog 定义在 models.system，非 models.models
            from sqlalchemy import select, desc
            async with self.container.db.get_session() as s:
                result = await s.execute(
                    select(ErrorLog).order_by(desc(ErrorLog.created_at)).limit(limit)
                )
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get error logs: {e}")
            return []

    def get_logs(self, lines: int = 50, log_type: str = "app") -> str:
        """读取系统日志最近 N 行 (优化版，防止大文件 OOM)"""
        if log_type == "error":
            log_file = settings.LOG_DIR / "error.log"
        else:
            log_file = settings.LOG_DIR / "app.log"
            
        if not log_file.exists():
            return "Log file not found."
            
        try:
            file_size = log_file.stat().st_size
            # 优化策略：仅读取末尾 200KB (约 1000-2000 行)，足以覆盖 N=50/100/200 的请求
            # 避免 readlines() 加载几百 MB 甚至 GB 的全量日志导致 OOM
            read_bytes = min(file_size, 200 * 1024) 
            
            with open(log_file, "rb") as f:
                if file_size > read_bytes:
                    f.seek(file_size - read_bytes)
                
                content = f.read().decode("utf-8", errors="ignore")
                all_lines = content.splitlines()
                
                # 如果文件被截断了，第一行可能不完整，丢弃它
                if file_size > read_bytes and len(all_lines) > 1:
                    all_lines = all_lines[1:]
                
                return "\n".join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"Read log failed: {e}")
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
        异步执行数据库备份 (统一接入 BackupService)
        """
        try:
            from .backup_service import backup_service
            path = await backup_service.backup_db(label="system_service")
            
            if path:
                size = os.path.getsize(str(path)) / (1024 * 1024)
                return {
                    "success": True, 
                    "path": str(path), 
                    "size_mb": size
                }
            else:
                return {
                    "success": False, 
                    "error": "备份服务未返回路径"
                }
        except Exception as e:
            logger.error(f"SystemService Backup failed: {e}")
            return {
                "success": False, 
                "error": str(e)
            }

    async def get_backup_info(self) -> Dict[str, Any]:
        """获取数据库备份统计信息"""
        backup_dir = settings.BACKUP_DIR
        try:
            if not backup_dir.exists():
                return {"last_backup": "从未", "backup_count": 0}
            
            backups = sorted(
                [f for f in backup_dir.iterdir() if f.suffix == ".bak" or f.suffix == ".zip"],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if not backups:
                return {"last_backup": "从未", "backup_count": 0}
            
            last_backup_time = datetime.fromtimestamp(backups[0].stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            return {
                "last_backup": last_backup_time,
                "backup_count": len(backups)
            }
        except Exception as e:
            logger.error(f"Failed to get backup info: {e}")
            return {"last_backup": "未知", "backup_count": 0}

    async def get_cleanup_info(self) -> Dict[str, Any]:
        """获取临时文件和缓存大小信息"""
        try:
            temp_dir = settings.TEMP_DIR
            log_dir = settings.LOG_DIR
            
            def get_dir_size(path: Path) -> float:
                if not path.exists(): return 0
                return sum(f.stat().st_size for f in path.rglob('*') if f.is_file()) / (1024 * 1024)

            tmp_size = get_dir_size(temp_dir)
            log_size = get_dir_size(log_dir)
            
            # 获取去重缓存大小
            from services.dedup.engine import smart_deduplicator
            dedup_stats = smart_deduplicator.get_stats()
            
            return {
                "tmp_size_mb": f"{round(tmp_size, 1)}MB",
                "log_size_mb": f"{round(log_size, 1)}MB",
                "dedup_cache_size": f"{round(dedup_stats.get('memory_mb', 0), 1)}MB" if 'memory_mb' in dedup_stats else f"{dedup_stats.get('cached_signatures', 0)}条"
            }
        except Exception as e:
            logger.error(f"Failed to get cleanup info: {e}")
            return {"tmp_size_mb": "0MB", "log_size_mb": "0MB", "dedup_cache_size": "0条"}

    async def restore_database(self, backup_path: str) -> Dict:
        """
        异步恢复数据库备份
        """
        try:
            if not os.path.exists(backup_path):
                return {"success": False, "error": "Backup file not found"}

            if settings.DATABASE_URL.startswith("sqlite"):
                path_str = settings.DATABASE_URL.split("///")[-1]
                db_path = str(Path(path_str).resolve())
                
                # 停止所有活动连接可以通过关闭引擎或是让用户手动重启
                # 这里简单处理：直接文件复制（注意：这在活跃连接下可能导致损坏或锁错误）
                import shutil
                shutil.copy2(backup_path, db_path)
                return {"success": True}
            else:
                return {"success": False, "error": "Only SQLite restore is supported"}
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"success": False, "error": str(e)}

    async def run_db_optimization(self, deep: bool = False) -> Dict[str, Any]:
        """运行数据库优化 (SQLite PRAGMA optimize/VACUUM)"""
        try:
            from core.db_factory import async_vacuum_database, async_analyze_database
            import time
            
            start_time = time.time()
            
            if deep:
                # Deep 模式：执行 VACUUM (无法在事务内运行，使用 factory 提供的独立连接)
                logger.info("Executing deep database optimization (VACUUM)...")
                await async_vacuum_database()
            else:
                # Standard 模式：执行 PRAGMA optimize
                from core.container import container
                from sqlalchemy import text
                async with container.db.get_session() as session:
                    await session.execute(text("PRAGMA optimize;"))
                    await session.commit()
            
            # 无论哪种模式都更新统计信息
            await async_analyze_database()
            
            # 清理旧日志 (暂定 30 天)
            deleted_logs = 0
            if deep:
                from models.models import async_cleanup_old_logs
                deleted_logs = await async_cleanup_old_logs(30)
            
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

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态信息"""
        import psutil
        from version import get_version
        from services.update_service import update_service
        
        try:
            process = psutil.Process()
            with process.oneshot():
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                create_time = process.create_time()
                
            uptime_seconds = time.time() - create_time
            uptime_str = self._format_uptime(uptime_seconds)
            
            # 版本信息
            version_str = get_version()
            git_ver = await update_service.get_current_version()
            if git_ver:
                version_str += f" ({git_ver})"
            elif not update_service._is_git_repo:
                version_str += " (非 Git 仓库)"

            disk = psutil.disk_usage(str(settings.BASE_DIR))
            
            # 获取 Worker 性能统计
            worker_stats = {}
            try:
                from core.container import container
                if hasattr(container, 'worker') and container.worker:
                    worker_stats = container.worker.get_performance_stats()
            except Exception: pass

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": round(process.memory_percent(), 1),
                "memory_used_mb": round(memory_info.rss / 1024 / 1024, 1),
                "disk_percent": disk.percent,
                "uptime": uptime_str,
                "version": version_str,
                "worker": worker_stats
            }
        except Exception as e:
            logger.error(f"Get system status failed: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_used_mb": 0,
                "disk_percent": 0,
                "uptime": "Unknown",
                "version": "Unknown"
            }

    def _format_uptime(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        if d > 0:
            return f"{int(d)}天 {int(h)}小时"
        elif h > 0:
            return f"{int(h)}小时 {int(m)}分"
        else:
            return f"{int(m)}分 {int(s)}秒"

    async def get_advanced_stats(self) -> Dict[str, Any]:
        """获取深度汇总统计信息 (整合官方API和HLL)"""
        from sqlalchemy import func, select
        from models.models import ForwardRule, Chat, MediaSignature, ErrorLog
        from services.network.api_optimization import get_api_optimizer
        from core.algorithms.hll import GlobalHLL
        
        async with self.container.db.get_session() as s:
            # 1. 基础规则统计
            stmt_count = select(func.count()).select_from(ForwardRule)
            rule_count = (await s.execute(stmt_count)).scalar() or 0
            
            stmt_active = select(func.count()).select_from(ForwardRule).where(ForwardRule.enable_rule.is_(True))
            active_rules = (await s.execute(stmt_active)).scalar() or 0
            
            # 2. 其他基础计数
            chat_count = (await s.execute(select(func.count()).select_from(Chat))).scalar() or 0
            media_count = (await s.execute(select(func.count()).select_from(MediaSignature))).scalar() or 0
            error_count = (await s.execute(select(func.count()).select_from(ErrorLog))).scalar() or 0
            total_processed = (await s.execute(select(func.sum(ForwardRule.message_count)).select_from(ForwardRule))).scalar() or 0
            
            # 3. HLL 估值
            unique_today = 0
            hll = GlobalHLL.get_hll("unique_messages_today")
            if hll: unique_today = hll.count()
            
            # 4. 官方 API 实时统计
            realtime_data = {}
            api_optimizer = get_api_optimizer()
            if api_optimizer:
                active_chat_ids = (await s.execute(select(Chat.telegram_chat_id).where(Chat.is_active == True).limit(5))).scalars().all()
                if active_chat_ids:
                    realtime_data = await api_optimizer.get_multiple_chat_statistics([cid for cid in active_chat_ids if cid])
            
            return {
                "base": {
                    "total_rules": rule_count,
                    "active_rules": active_rules,
                    "chat_count": chat_count,
                    "media_count": media_count,
                    "error_count": error_count,
                    "total_processed": total_processed,
                },
                "unique_today": unique_today,
                "realtime": realtime_data,
                "api_enabled": api_optimizer is not None
            }

    async def run_anomaly_detection(self) -> Dict[str, Any]:
        """扫描消息日志中的异常模式"""
        try:
            from models.models import RuleLog
            from sqlalchemy import select, func
            
            async with self.container.db.get_session() as session:
                # 检查最近 1 小时的失败数
                one_hour_ago = datetime.now() - timedelta(hours=1)
                stmt_total = select(func.count(RuleLog.id)).where(RuleLog.created_at >= one_hour_ago)
                total_recent = (await session.execute(stmt_total)).scalar() or 0
                
                if total_recent == 0:
                    return {"status": "normal", "message": "最近 1 小时由于无转发数据，暂未发现异常。"}
                
                stmt_err = select(func.count(RuleLog.id)).where(
                    RuleLog.status == "error",
                    RuleLog.created_at >= one_hour_ago
                )
                recent_errors = (await session.execute(stmt_err)).scalar() or 0
                error_rate = (recent_errors / total_recent) * 100
                
                if error_rate > 30: # 失败率超过 30%
                    return {
                        "status": "warning", 
                        "message": f"🚨 [高失败率告警] 最近 1 小时失败率达 {error_rate:.1f}% ({recent_errors}/{total_recent})，请检查网络或目标频道权限。"
                    }
                
                return {"status": "healthy", "message": "✅ 未检测到大规模转发异常，系统运行平稳。"}
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {"status": "error", "message": str(e)}

    async def export_analytics_csv(self) -> Optional[Path]:
        """导出最近 24 小时的转发统计到 CSV"""
        try:
            import csv
            from models.models import RuleLog
            from sqlalchemy import select
            
            os.makedirs(settings.TEMP_DIR, exist_ok=True)
            export_path = settings.TEMP_DIR / f"analytics_export_{int(time.time())}.csv"
            one_day_ago = datetime.now() - timedelta(days=1)
            
            async with self.container.db.get_session() as session:
                stmt = select(RuleLog).where(RuleLog.created_at >= one_day_ago).order_by(RuleLog.created_at.desc()).limit(1000)
                logs = (await session.execute(stmt)).scalars().all()
                
                if not logs:
                    return None
                    
                with open(export_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Time", "RuleID", "Type", "Status", "Latency"])
                    for log in logs:
                        writer.writerow([
                            log.id, 
                            log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            log.rule_id,
                            log.message_type,
                            log.status,
                            f"{log.latency:.3f}s" if log.latency else "0s"
                        ])
                
                return export_path
        except Exception as e:
            logger.error(f"Export CSV failed: {e}")
            return None

    async def get_db_pragma_info(self) -> Dict[str, Any]:
        """获取 SQLite 的 PRAGMA 配置信息"""
        try:
            from sqlalchemy import text
            async with self.container.db.get_session() as session:
                # 获取 auto_vacuum
                res_v = await session.execute(text("PRAGMA auto_vacuum;"))
                auto_vacuum = res_v.scalar()
                
                # 获取 journal_mode
                res_j = await session.execute(text("PRAGMA journal_mode;"))
                journal_mode = res_j.scalar()
                
                # 获取 synchronous
                res_s = await session.execute(text("PRAGMA synchronous;"))
                synchronous = res_s.scalar()
                
                # 获取 mmap_size
                res_m = await session.execute(text("PRAGMA mmap_size;"))
                mmap_size = res_m.scalar()
                
                return {
                    "auto_vacuum": bool(auto_vacuum) if isinstance(auto_vacuum, int) else auto_vacuum != 'NONE',
                    "wal_mode": str(journal_mode).upper() == 'WAL',
                    "sync_mode": 'NORMAL' if synchronous == 1 else 'FULL' if synchronous == 2 else 'OFF' if synchronous == 0 else str(synchronous),
                    "mmap_size": f"{int(mmap_size) / 1024 / 1024:.0f}MB" if mmap_size and int(mmap_size) > 0 else "0 (Disabled)"
                }
        except Exception as e:
            logger.error(f"Failed to get DB PRAGMA info: {e}")
            return {'auto_vacuum': False, 'wal_mode': False, 'sync_mode': 'Unknown'}

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
        self._memory_limit_mb = settings.MEMORY_CRITICAL_THRESHOLD_MB
        self._memory_warning_mb = settings.MEMORY_WARNING_THRESHOLD_MB

    def get_stats(self) -> Dict[str, Any]:
        """获取守护服务的当前统计状态"""
        import psutil
        try:
            process = psutil.Process()
            return {
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "cpu_percent": process.cpu_percent(),
                "uptime_seconds": round(time.time() - process.create_time(), 1),
                "tasks_active": len(asyncio.all_tasks()),
                "guard_status": "active" if not self._stop_event.is_set() else "stopped"
            }
        except Exception:
            return {"status": "error"}

    def start_guards(self):
        """Deprecated: Use start_guards_async instead."""
        
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
                            except OSError as e:
                                logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                    
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
                            except Exception as e:
                                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                        
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
                    # [修复] 如果系统当前正处于更新后的“观察期”，则屏蔽热重启，防止造成启动循环导致误判回滚
                    from services.update_service import update_service
                    update_state = update_service._get_state()
                    if update_state.get("status") == "restarting":
                        logger.warning(f"⚠️ [guard-watcher] 系统处于更新观察期 (Observation Period)，已忽略文件变更以防止启动循环: {changed}")
                    else:
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
            
            # 物理重启尝试
            logger.info("Attempting physical process re-exec...")
            import os
            import sys
            import time
            
            # 获取当前运行的 Python 解释器和参数
            executable = sys.executable
            args = sys.argv[:]
            
            # [成熟方案] 给予一小段时间释放资源和日志句柄
            # 虽然 coordinator.shutdown 已完成，但在 Windows 上文件锁释放有时有延迟
            time.sleep(0.5)
            
            if os.name == 'nt':
                # Windows 下 os.execl 是通过 spawn 模拟的，会生成新进程并终止当前进程
                # 这种方式在 Windows 下是高度可靠的，能确保锁被释放
                os.execl(executable, executable, *args)
            else:
                # Unix 下 os.execl 替换当前进程映像，极致平滑
                os.execl(executable, executable, *args)
                
            # 理论上 execl 不会执行到这里，除非找不到文件
            sys.exit(0)
        except Exception as e:
            logger.error(f"Graceful restart failed: {e}")
            # 最后的保底退出
            sys.exit(1)

    def trigger_restart(self):
        asyncio.create_task(self._restart_process_async())

    async def cleanup_old_logs(self, days: int) -> Dict[str, Any]:
        """清理旧日志 (Handler Purity 兼容)"""
        try:
            from core.db_factory import async_cleanup_old_logs
            deleted_count = await async_cleanup_old_logs(days)
            logger.info(f"成功清理 {days} 天前的日志，删除 {deleted_count} 条记录")
            return {
                'success': True,
                'deleted_count': deleted_count
            }
        except Exception as e:
            logger.error(f"清理日志失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'deleted_count': 0
            }

    async def get_db_health(self) -> Dict[str, Any]:
        """获取数据库健康状态 (Handler Purity 兼容)"""
        try:
            from sqlalchemy import text
            async with self.container.db.get_session() as session:
                # 简单的连接测试
                await session.execute(text("SELECT 1"))
                return {
                    'connected': True,
                    'status': 'healthy'
                }
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return {
                'connected': False,
                'status': 'error',
                'error': str(e)
            }


system_service = SystemService()
guard_service = GuardService()
