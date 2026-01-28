
import asyncio
import datetime
import logging
import os

from core.config import settings
from scheduler.db_archive_job import archive_once, garbage_collect_once
from repositories.archive_store import compact_small_files
from core.helpers.metrics import ARCHIVE_RUN_SECONDS, ARCHIVE_RUN_TOTAL

logger = logging.getLogger(__name__)

class CronService:
    def __init__(self):
        self._tasks = []

    def start(self):
        self._tasks.append(asyncio.create_task(self._archive_cron(), name="archive_cron"))
        self._tasks.append(asyncio.create_task(self._compact_cron(), name="compact_cron"))
        self._tasks.append(asyncio.create_task(self._cleanup_temp_cron(), name="cleanup_temp_cron"))
        logger.info("CronService started")

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        self._tasks.clear()
        
    async def _archive_cron(self):
        times = settings.CLEANUP_CRON_TIMES
        while True:
            try:
                now = datetime.datetime.now()
                deltas = []
                for t in times:
                    try:
                        if isinstance(t, str):
                            hh, mm = [int(x) for x in t.split(':')]
                        else:
                            continue
                    except Exception:
                        continue
                        
                    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                    if target <= now:
                        target += datetime.timedelta(days=1)
                    deltas.append((target - now).total_seconds())
                
                sleep_s = min(deltas) if deltas else 86400
                await asyncio.sleep(sleep_s)
                
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    break
                    
                if settings.AUTO_ARCHIVE_ENABLED:
                    start = loop.time()
                    status = 'success'
                    try:
                        await loop.run_in_executor(None, archive_once)
                    except Exception:
                        status = 'error'
                    finally:
                        duration = loop.time() - start
                        ARCHIVE_RUN_SECONDS.observe(duration)
                        ARCHIVE_RUN_TOTAL.labels(status=status).inc()
                        
                if settings.AUTO_GC_ENABLED:
                    try:
                        await loop.run_in_executor(None, garbage_collect_once)
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Archive cron error: {e}")
                await asyncio.sleep(60)

    async def _compact_cron(self):
        while True:
            try:
                if not settings.ARCHIVE_COMPACT_ENABLED:
                    await asyncio.sleep(3600)
                    continue
                now = datetime.datetime.now()
                target = now.replace(hour=4, minute=30, second=0, microsecond=0)
                if target <= now:
                    target += datetime.timedelta(days=1)
                await asyncio.sleep((target - now).total_seconds())
                
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    break
                    
                await loop.run_in_executor(None, compact_small_files, 'media_signatures', settings.ARCHIVE_COMPACT_MIN_FILES)
            except asyncio.CancelledError:
                break
            except Exception:
                 await asyncio.sleep(3600)

    async def _cleanup_temp_cron(self):
        """定期清理临时文件"""
        while True:
            try:
                # 每小时执行一次
                await asyncio.sleep(3600)
                logger.info("开始定时清理临时目录...")
                count = await self._clear_temp_dir_async()
                logger.info(f"定时清理完成，删除了 {count} 个文件")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定时清理临时目录失败: {e}")
                await asyncio.sleep(60) # 出错后等待一分钟

    async def _clear_temp_dir_async(self):
        """异步版本的临时目录清理"""
        try:
            count = await asyncio.to_thread(self._clear_temp_dir_sync)
            return count
        except Exception as e:
            logger.warning(f"清理临时目录失败: {e}")
            return 0
            
    def _clear_temp_dir_sync(self):
        """同步版本的临时目录清理"""
        count = 0
        if not settings.TEMP_DIR.exists():
            return 0
            
        for file in os.listdir(settings.TEMP_DIR):
            try:
                file_path = os.path.join(settings.TEMP_DIR, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            except Exception:
                pass
        return count

cron_service = CronService()
