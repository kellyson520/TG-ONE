from typing import Optional
import asyncio
from services.settings import settings
from utils.helpers.metrics import ARCHIVE_RUN_SECONDS, ARCHIVE_RUN_TOTAL
from core.container import container


def _parse_time(t: str):
    try:
        hh, mm = [int(x) for x in t.split(":")]
        return hh, mm
    except Exception:
        return None


def setup_apscheduler() -> Optional[object]:
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except Exception:
        return None
    from scheduler.db_archive_job import archive_once, garbage_collect_once
    from utils.archive_store import compact_small_files
    sch = AsyncIOScheduler()
    async def maintenance_job():
        if settings.auto_archive_enabled:
            try:
                loop = asyncio.get_event_loop()
                start = loop.time()
                status = 'success'
                try:
                    await asyncio.to_thread(archive_once)
                except Exception:
                    status = 'error'
                finally:
                    duration = loop.time() - start
                    ARCHIVE_RUN_SECONDS.observe(duration)
                    ARCHIVE_RUN_TOTAL.labels(status=status).inc()
            except Exception:
                pass
        if settings.auto_gc_enabled:
            try:
                await asyncio.to_thread(garbage_collect_once)
            except Exception:
                pass
    for t in settings.cleanup_cron_times:
        parsed = _parse_time(t)
        if not parsed:
            continue
        h, m = parsed
        sch.add_job(maintenance_job, "cron", hour=h, minute=m, id=f"maintenance_{h}_{m}", coalesce=True, max_instances=1, misfire_grace_time=600)
    if settings.archive_compact_enabled:
        h, m = 4, 30
        async def compact_job():
            try:
                await asyncio.to_thread(compact_small_files, "media_signatures", settings.archive_compact_min_files)
            except Exception:
                pass
        sch.add_job(compact_job, "cron", hour=h, minute=m, id="compact_media_signatures", coalesce=True, max_instances=1, misfire_grace_time=600)
    
    # 添加僵尸任务救援任务，每5分钟运行一次
    async def zombie_rescue_job():
        try:
            # 从容器中获取 task_repo 实例
            if hasattr(container, 'task_repo'):
                await container.task_repo.rescue_stuck_tasks()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"僵尸任务救援失败: {e}")
    
    # 每5分钟运行一次僵尸任务救援
    sch.add_job(zombie_rescue_job, "interval", minutes=5, id="zombie_task_rescuer", coalesce=True, max_instances=1, misfire_grace_time=600)
    
    sch.start()
    return sch