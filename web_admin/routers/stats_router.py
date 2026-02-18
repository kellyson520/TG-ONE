
import logging
import traceback
import psutil
from fastapi import APIRouter, Depends, Query, Request
from pathlib import Path
from web_admin.schemas.response import ResponseSchema
from sqlalchemy import select

from core.container import container
from web_admin.security.deps import login_required

from services.dedup.engine import smart_deduplicator
from services.forward_service import forward_service
from core.helpers.realtime_stats import realtime_stats_cache
from core.cache.unified_cache import get_cache_stats
from services.network.bot_heartbeat import get_heartbeat
from models.models import async_get_db_health
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["Stats"])

@router.get("/overview", response_model=ResponseSchema)
async def api_stats_overview(request: Request, user = Depends(login_required)):
    """获取统计总览 (统一入口)"""
    try:
        from services.analytics_service import analytics_service
        
        # 1. 获取基础概览
        overview = await analytics_service.get_analytics_overview()
        
        # 2. 获取性能指标
        perf = await analytics_service.get_performance_metrics()
        
        # 3. 获取服务状态
        system_status = await analytics_service.get_system_status()
        
        data = {
            'overview': overview.get('overview', {}),
            'forward_stats': overview.get('forward_stats', {}),
            'dedup_stats': overview.get('dedup_stats', {}),
            'system_resources': perf.get('system_resources', {}),
            'queue_status': perf.get('queue_status', {}),
            'performance': perf.get('performance', {}),
            'service_status': system_status.get('service_status', {
                'bot': 'running' if overview.get('forward_stats', {}).get('total_forwards', 0) > 0 else 'unknown',
                'api': 'running',
                'db': 'running'
            })
        }
        
        return ResponseSchema(success=True, data=data)
    except Exception as e:
        logger.error(f"Error in api_stats_overview: {str(e)}\n{traceback.format_exc()}")
        return ResponseSchema(success=False, error=str(e))


@router.get("/system_resources", response_model=ResponseSchema)
async def api_system_resources(request: Request, user = Depends(login_required)):

    """获取系统资源使用情况（CPU、内存、磁盘、网络）"""
    try:
        # CPU使用率 - 非阻塞模式，避免冻结事件循环
        # interval=None 返回自上次调用以来的统计，耗时几乎为 0
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # 内存使用率
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_used_mb = mem.used / (1024 * 1024)
        
        # 磁盘使用率
        # 根据操作系统可能是 '/' 或 'C:'
        import platform
        path = '/'
        if platform.system() == 'Windows':
            path = 'C:\\'
            
        disk = psutil.disk_usage(path)
        disk_percent = disk.percent
        
        # 数据库大小
        db_size_mb = 0
        try:
            db_path = Path(settings.DB_PATH)
            if db_path.exists():
                db_size_mb = db_path.stat().st_size / (1024 * 1024)
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        
        # 活跃连接数 (模拟或从DBPool获取)
        active_connections = 0
        try:
            from models.models import get_async_engine
            engine = get_async_engine()
            if hasattr(engine.pool, 'checkedout'):
                active_connections = engine.pool.checkedout()
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            
        # 队列大小
        queue_size = 0
        try:
            queue_status = await container.task_repo.get_queue_status()
            queue_size = queue_status.get('active_queues', 0)
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            
        data = {
            'cpu_percent': cpu_percent,
            'memory_percent': mem_percent,
            'memory_used_mb': round(mem_used_mb, 1),
            'disk_percent': disk_percent,
            'db_size_mb': round(db_size_mb, 1),
            'active_connections': active_connections,
            'queue_size': queue_size
        }
        
        return ResponseSchema(success=True, data=data)
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.get("/series", response_model=ResponseSchema)
async def api_stats_series(
    request: Request,
    period: str = Query('7d'),
    days: int = Query(7, ge=1, le=30),
    user = Depends(login_required)
):

    """获取统计系列数据"""
    try:
        from datetime import datetime, timedelta
        
        from services.analytics_service import analytics_service
        
        if period and period.lower() == '24h':
            # 获取跨层 24 小时趋势
            trend_data = await analytics_service.get_unified_hourly_trend(hours=24)
            
            labels = []
            series = []
            for item in trend_data:
                hour_part = item['hour'].split('T')[1] if 'T' in item['hour'] else item['hour']
                labels.append(f"{hour_part}:00")
                series.append(item['count'])
            
            return ResponseSchema(
                success=True, 
                data={
                    'labels': labels, 
                    'series': series,
                    'title': '24小时转发趋势'
                }
            )

        # 默认转发趋势 (跨层汇总)
        labels = []
        series = []
        for i in range(days-1, -1, -1):
            date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            summary = await analytics_service.get_daily_summary(date_str)
            
            # '2026-01-13' -> '01-13'
            short_date = '-'.join(date_str.split('-')[1:])
            labels.append(short_date)
            series.append(summary.get('total_forwards', 0))
            
        return ResponseSchema(
            success=True, 
            data={
                'labels': labels, 
                'series': series,
                'title': f'{days}天转发趋势'
            }
        )

            
    except Exception as e:
        logger.error(f"Error in api_stats_series: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.get("/distribution", response_model=ResponseSchema)
async def api_stats_distribution(
    request: Request,
    user = Depends(login_required)
):

    """获取消息类型分布统计"""
    try:
        from services.analytics_service import analytics_service
        stats = await analytics_service.get_detailed_stats(days=1)
        dist = stats.get('type_distribution', [])
        
        # 转换格式为前端饼图需要的格式 {value: x, name: y}
        formatted_data = []
        for item in dist:
            formatted_data.append({
                'value': item.get('count', 0),
                'name': item.get('type', 'Unknown')
            })
            
        return ResponseSchema(success=True, data=formatted_data)
    except Exception as e:
        logger.error(f"Error in api_stats_distribution: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.get("/system", response_model=ResponseSchema)
async def api_stats_system(request: Request, user = Depends(login_required)):

    """获取系统内部详细状态 (Scheduler, Cache, RSS Service)"""
    try:
        # RSS Service Stats
        rss_stats = {}
        if container.rss_puller:
            try:
                rss_stats = container.rss_puller.get_service_stats()
            except Exception as e:
                rss_stats = {"error": str(e)}
        else:
            rss_stats = {"status": "not_initialized"}
            
        # Cache Stats
        cache_stats = {}
        try:
             cache_stats = get_cache_stats()
        except Exception as e:
             cache_stats = {"error": str(e)}
             
        # Combined
        data = {
            "rss_service": rss_stats,
            "cache_system": cache_stats,
            "timestamp": "now"
        }
        return ResponseSchema(success=True, data=data)
        
    except Exception as e:
        logger.error(f"Error in api_stats_system: {e}")
        return ResponseSchema(success=False, error=str(e))
