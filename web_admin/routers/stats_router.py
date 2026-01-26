
import logging
import traceback
import psutil
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from core.container import container
from web_admin.security.deps import login_required
# from utils.core.env_config import env_config_manager
from services.dedup.engine import smart_deduplicator
from services.system_service import guard_service
from services.forward_service import forward_service
from core.helpers.realtime_stats import realtime_stats_cache
from utils.processing.unified_cache import get_cache_stats
from services.network.bot_heartbeat import get_heartbeat
from models.models import get_db_health, async_get_db_health
from core.config import settings
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["Stats"])

@router.get("/overview", response_class=JSONResponse)
async def api_stats_overview(request: Request, user = Depends(login_required)):
    """获取统计总览"""
    try:
        # 初始化统计数据
        base = {}
        perf = {}
        
        # 获取系统资源使用情况
        sys_res = {}
        try:
            local_sys = await realtime_stats_cache.get_system_stats(force_refresh=True)
            if isinstance(local_sys, dict):
                sys_res = local_sys.get('system_resources', {})
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
        
        # 获取队列状态
        queue_status = {}
        try:
            # ✅ 调用 Repository，逻辑收敛
            queue_status = await container.task_repo.get_queue_status()
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            pass
        
        # 获取规则统计
        overview = {}
        try:
            # ✅ 调用 Repository，逻辑收敛
            rule_stats = await container.task_repo.get_rule_stats()
            overview = {
                'total_rules': rule_stats['total_rules'],
                'active_rules': rule_stats['active_rules'],
                'total_chats': rule_stats['total_chats']
            }
        except Exception as e:
            logger.error(f"Error getting stats overview: {e}\n{traceback.format_exc()}")
            overview = {'total_rules': 0, 'active_rules': 0, 'total_chats': 0, 'error': str(e)}
        
        # 获取转发统计
        forward_stats = {'total_forwards': 0}
        try:
            fs = await forward_service.get_forward_stats()
            if isinstance(fs, dict):
                ft = int(((fs.get('today') or {}).get('total_forwards') or 0))
                if ft >= 0:
                    forward_stats = {'total_forwards': ft}
                    # logger.info(f"统计总览使用业务层数据: today_total={ft}")
        except Exception as e:
            logger.warning(f"统计总览获取业务层转发统计失败: {e}")
        
        # 获取去重统计
        dedup_stats = {'cached_signatures': 0}
        try:
            dedup = smart_deduplicator.get_stats()
            dedup_stats = {'cached_signatures': int(dedup.get('cached_signatures', 0))}
        except Exception as e:
            logger.error(f"Error getting dedup stats: {e}")
        
        # 构建性能指标
        perf = {
            'system_resources': sys_res,
            'queue_status': {
                'active_queues': queue_status.get('active_queues', 0),
                'avg_delay': '0s',
                'error_rate': queue_status.get('error_rate', 0)
            },
            'performance': {}
        }
        
        system_resources = perf.get('system_resources', {})
        queue_status = perf.get('queue_status', {})
        performance = perf.get('performance', {})
        
        # 服务状态检查 - 移除自引用 HTTP 请求防止单线程死锁
        api_status = 'running'
        ready_status = 'running'
        
        try:
            db_health = await async_get_db_health()
            if not db_health.get('connected'):
                api_status = 'warning'
        except Exception:
            api_status = 'stopped'

        try:
            bt = settings.BOT_TOKEN
            api_id = settings.API_ID
            user_id = os.getenv('USER_ID')
            cfg_ready = bool(str(bt or '').strip()) and bool(str(api_id or '').strip()) and bool(str(user_id or '').strip())
            if not cfg_ready:
                ready_status = 'warning'
        except Exception:
            ready_status = 'stopped'
        
        db = {}
        try:
            db = await async_get_db_health()
        except Exception:
            db = {}
        db_status = 'running' if bool(db.get('connected')) else 'stopped'
        
        # Bot 状态检查 - 使用线程池避免网络请求阻塞
        bot_status = 'unknown'
        try:
            from fastapi.concurrency import run_in_threadpool
            hb = await run_in_threadpool(get_heartbeat)
            age = float(hb.get('age_seconds') or 9999)
            hbs = str(hb.get('status') or '')
            if hbs == 'running' and age < 180:
                bot_status = 'running'
            elif hbs:
                bot_status = 'stopped'
        except Exception:
            bot_status = 'unknown'
        
        try:
            if bot_status == 'unknown':
                if int(forward_stats.get('total_forwards', 0)) > 0:
                    bot_status = 'running'
                elif api_status == 'running' and db_status == 'running':
                    bot_status = 'running'
        except Exception:
            pass
        
        try:
            dedup_conf = smart_deduplicator.config or {}
        except Exception:
            dedup_conf = {}
        dedup_enabled = bool(dedup_conf.get('enable_time_window')) or bool(dedup_conf.get('enable_content_hash')) or bool(dedup_stats.get('cached_signatures'))
        dedup_state = 'running' if dedup_enabled else 'stopped'
        
        data = {
            'overview': overview,
            'forward_stats': forward_stats,
            'dedup_stats': dedup_stats,
            'system_resources': system_resources,
            'queue_status': queue_status,
            'performance': performance,
            'service_status': {
                'bot': bot_status,
                'api': api_status,
                'db': db_status,
                'ready': ready_status,
                'dedup': dedup_state
            }
        }
        
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error in api_stats_overview: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/system_resources", response_class=JSONResponse)
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
            import os
            # Try to get path from settings.DB_URL if it is sqlite
            db_url = str(settings.DB_URL or '')
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
        except Exception:
            pass
        
        # 活跃连接数 (模拟或从DBPool获取)
        active_connections = 0
        try:
            from models.models import get_async_engine
            engine = get_async_engine()
            if hasattr(engine.pool, 'checkedout'):
                active_connections = engine.pool.checkedout()
        except Exception:
            pass
            
        # 队列大小
        queue_size = 0
        try:
            queue_status = await container.task_repo.get_queue_status()
            queue_size = queue_status.get('active_queues', 0)
        except Exception:
            pass
            
        data = {
            'cpu_percent': cpu_percent,
            'memory_percent': mem_percent,
            'memory_used_mb': round(mem_used_mb, 1),
            'disk_percent': disk_percent,
            'db_size_mb': round(db_size_mb, 1),
            'active_connections': active_connections,
            'queue_size': queue_size
        }
        
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/series", response_class=JSONResponse)
async def api_stats_series(
    request: Request,
    period: str = Query('7d'),
    days: int = Query(7, ge=1, le=30),
    user = Depends(login_required)
):
    """获取统计系列数据"""
    try:
        from datetime import datetime, timedelta
        
        if period and period.lower() == '24h':
            # 获取最近 24 小时的每小时趋势
            trend_data = await container.stats_repo.get_hourly_trend(24)
            
            # 格式化前端需要的 labels 和 series
            labels = []
            series = []
            
            # 为了确保图表连续，我们可以补齐缺失的小时，或者直接使用返回的数据
            # 这里简单直接使用返回的数据
            for item in trend_data:
                # '2026-01-13T10' -> '10:00'
                hour_part = item['hour'].split('T')[1] if 'T' in item['hour'] else item['hour']
                labels.append(f"{hour_part}:00")
                series.append(item['count'])
            
            return JSONResponse({
                'success': True, 
                'data': {
                    'labels': labels, 
                    'series': series,
                    'title': '24小时转发趋势'
                }
            })
        
        # 默认返回 7 天内的每日趋势
        # 我们可以从 RuleStatistics 表聚合
        async with container.db.session() as session:
            from models.models import RuleStatistics
            from sqlalchemy import func
            
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # 按日期聚合所有规则的成功转发数
            stmt = (
                select(
                    RuleStatistics.date,
                    func.sum(RuleStatistics.forwarded_count).label('count')
                )
                .where(RuleStatistics.date >= cutoff_date)
                .group_by(RuleStatistics.date)
                .order_by(RuleStatistics.date)
            )
            
            result = await session.execute(stmt)
            labels = []
            series = []
            
            for row in result:
                # '2026-01-13' -> '01-13'
                short_date = '-'.join(row.date.split('-')[1:])
                labels.append(short_date)
                series.append(int(row.count or 0))
                
            # 如果没数据，返回最近几天的空占位 (可选)
            if not labels:
                for i in range(days-1, -1, -1):
                    d = (datetime.now() - timedelta(days=i)).strftime('%m-%d')
                    labels.append(d)
                    series.append(0)
            
            return JSONResponse({
                'success': True, 
                'data': {
                    'labels': labels, 
                    'series': series,
                    'title': f'{days}天转发趋势'
                }
            })
            
    except Exception as e:
        logger.error(f"Error in api_stats_series: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/distribution", response_class=JSONResponse)
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
            
        return JSONResponse({'success': True, 'data': formatted_data})
    except Exception as e:
        logger.error(f"Error in api_stats_distribution: {e}")
        return JSONResponse({'success': False, 'error': str(e)})

@router.get("/system", response_class=JSONResponse)
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
        return JSONResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error in api_stats_system: {e}")
        return JSONResponse({'success': False, 'error': str(e)})
