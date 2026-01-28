import os
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse

from web_admin.security.deps import admin_required, login_required
from core.db_factory import get_async_engine
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System Stats"])

@router.get("/tasks", response_model=ResponseSchema)
async def get_tasks_list(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    user = Depends(admin_required),
    task_repo = Depends(deps.get_task_repo)
):
    """获取任务队列列表"""
    try:
        tasks, total = await task_repo.get_tasks(page, limit, status)
        
        data = []
        for t in tasks:
            data.append({
                'id': t.id,
                'type': t.task_type,
                'status': t.status,
                'priority': t.priority,
                'unique_key': t.unique_key,
                'grouped_id': t.grouped_id,
                'retry_count': t.retry_count,
                'error_log': t.error_log,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'updated_at': t.updated_at.isoformat() if t.updated_at else None,
                'scheduled_at': t.scheduled_at.isoformat() if t.scheduled_at else None
            })
            
        return ResponseSchema(
            success=True,
            data={
                'items': data,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
        )
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/stats", response_model=ResponseSchema)
async def get_system_stats(
    user = Depends(login_required),
    task_repo = Depends(deps.get_task_repo),
    forward_service = Depends(deps.get_forward_service),
    dedup = Depends(deps.get_dedup_engine),
    guard_service = Depends(deps.get_guard_service),
    stats_repo = Depends(deps.get_stats_repo)
):
    """获取系统运行核心指标"""
    try:
        # 1. 规则统计
        total_rules = 0
        active_rules = 0
        try:
            rule_stats = await task_repo.get_rule_stats()
            total_rules = rule_stats.get('total_rules', 0)
            active_rules = rule_stats.get('active_rules', 0)
        except Exception:
            pass
            
        # 2. 转发统计
        today_forwards = 0
        try:
            fs = await forward_service.get_forward_stats()
            if isinstance(fs, dict):
                today_forwards = int(((fs.get('today') or {}).get('total_forwards') or 0))
        except Exception:
            pass
            
        # 3. 去重统计
        dedup_count = 0
        try:
            dedup_stats = dedup.get_stats()
            dedup_count = dedup_stats.get('cached_signatures', 0) + dedup_stats.get('cached_content_hashes', 0)
        except Exception:
            pass
            
        # 4. 系统运行状况 (容器管理)
        guard_stats = {}
        try:
            guard_stats = guard_service.get_stats()
        except Exception:
            pass

        # 5. 趋势数据
        trend = []
        try:
            trend = await stats_repo.get_hourly_trend(24)
        except Exception:
            pass

        return ResponseSchema(
            success=True,
            data={
                'rules': {
                    'total': total_rules,
                    'active': active_rules,
                    'enabled_rate': round((active_rules / total_rules * 100), 1) if total_rules > 0 else 0
                },
                'forwards': {
                    'today': today_forwards,
                    'trend': trend
                },
                'dedup': {
                    'total_cached': dedup_count
                },
                'system': guard_stats
            }
        )
    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/db-pool", response_model=ResponseSchema)
async def get_db_pool_status(user = Depends(admin_required)):
    """
    获取数据库连接池状态
    Phase H.1: 数据库连接池优化
    """
    try:
        engine = get_async_engine()
        pool = engine.pool
        
        # SQLite 使用 NullPool 或 StaticPool，没有详细的连接池统计
        if hasattr(pool, 'checkedout'):
            pool_status = {
                "pool_type": pool.__class__.__name__,
                "checkedout": pool.checkedout(),  # 当前使用中的连接
                "checkedin": pool.checkedin(),    # 空闲连接
                "overflow": pool.overflow(),       # 溢出连接数
                "size": pool.size(),               # 配置的连接池大小
                "timeout": pool.timeout(),         # 超时时间
                "invalidated": getattr(pool, '_invalidate_time', None),
            }
        else:
            # SQLite 模式
            pool_status = {
                "pool_type": pool.__class__.__name__,
                "note": "SQLite uses StaticPool/NullPool, detailed stats unavailable"
            }
        
        # 配置信息
        config = {
            "DB_POOL_SIZE": os.environ.get('DB_POOL_SIZE', '20'),
            "DB_MAX_OVERFLOW": os.environ.get('DB_MAX_OVERFLOW', '30'),
            "DB_POOL_TIMEOUT": os.environ.get('DB_POOL_TIMEOUT', '60'),
            "DB_POOL_RECYCLE": os.environ.get('DB_POOL_RECYCLE', '3600'),
        }
        
        return ResponseSchema(
            success=True,
            data={
                'pool': pool_status,
                'config': config,
                'database_url': str(engine.url).split('@')[-1] if '@' in str(engine.url) else str(engine.url)  # 隐藏密码
            }
        )
    except Exception as e:
        logger.error(f"Error fetching DB pool status: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/eventbus/stats", response_model=ResponseSchema)
async def get_eventbus_stats(
    user = Depends(admin_required),
    bus = Depends(deps.get_event_bus)
):
    """获取 EventBus 事件统计"""
    try:
        stats = bus.get_stats()
        return ResponseSchema(success=True, data=stats)
    except Exception as e:
        logger.error(f"Error fetching EventBus stats: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/exceptions/stats", response_model=ResponseSchema)
async def get_exception_stats(
    user = Depends(admin_required),
    handler = Depends(deps.get_exception_handler)
):
    """获取全局异常处理器统计"""
    try:
        stats = handler.get_stats()
        return ResponseSchema(success=True, data=stats)
    except Exception as e:
        logger.error(f"Error fetching exception stats: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/websocket/stats", response_model=ResponseSchema)
async def get_websocket_stats(
    user = Depends(login_required),
    ws = Depends(deps.get_ws_manager)
):
    """获取 WebSocket 连接统计"""
    try:
        stats = ws.get_stats()
        return ResponseSchema(success=True, data=stats)
    except Exception as e:
        logger.error(f"Error fetching WebSocket stats: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/stats_fragment", response_class=HTMLResponse)
async def api_stats_fragment(
    request: Request, 
    user = Depends(login_required),
    task_repo = Depends(deps.get_task_repo),
    forward_service = Depends(deps.get_forward_service),
    dedup = Depends(deps.get_dedup_engine)
):
    """获取统计片段（用于HTMX更新）"""
    try:
        # 获取统计数据
        total_rules = 0
        active_rules = 0
        today_total = 0
        dedup_cache_size = 0
        
        # 获取规则统计
        try:
            rule_stats = await task_repo.get_rule_stats()
            total_rules = rule_stats['total_rules']
            active_rules = rule_stats['active_rules']
        except Exception as e:
            logger.error(f"Error getting rule stats: {e}")
            pass
        
        # 获取转发统计
        try:
            fs = await forward_service.get_forward_stats()
            if isinstance(fs, dict):
                today_total = int(((fs.get('today') or {}).get('total_forwards') or 0))
        except Exception as e:
            logger.warning(f"统计总览获取业务层转发统计失败: {e}")
        
        # 获取去重统计
        try:
            dedup_stats = dedup.get_stats()
            dedup_cache_size = dedup_stats.get('cached_signatures', 0) + dedup_stats.get('cached_content_hashes', 0)
        except Exception:
            pass
        
        # 计算活跃规则百分比
        active_percentage = 0
        if total_rules > 0:
            active_percentage = round((active_rules / total_rules) * 100)
        
        # 构建HTML响应
        html = f"""
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card metric-card primary h-100">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col">
                            <h6 class="text-uppercase text-muted mb-2 fw-semibold">
                                <i class="bi bi-gear"></i> 总规则数
                            </h6>
                            <div class="metric-value text-primary" id="totalRules">
                                {total_rules}
                            </div>
                            <div class="metric-change text-success" id="rulesChange">
                                <i class="bi bi-arrow-up"></i> +0 今日新增
                            </div>
                        </div>
                        <div class="col-auto">
                            <div class="bg-primary bg-opacity-10 p-3 rounded-circle">
                                <i class="bi bi-gear-fill text-primary" style="font-size: 2rem;"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card metric-card success h-100">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col">
                            <h6 class="text-uppercase text-muted mb-2 fw-semibold">
                                <i class="bi bi-check-circle"></i> 活跃规则
                            </h6>
                            <div class="metric-value text-success" id="activeRules">
                                {active_rules}
                            </div>
                            <div class="metric-change text-muted" id="activePercentage">
                                <i class="bi bi-percent"></i> {active_percentage}% 启用率
                            </div>
                        </div>
                        <div class="col-auto">
                            <div class="bg-success bg-opacity-10 p-3 rounded-circle">
                                <i class="bi bi-check-circle-fill text-success" style="font-size: 2rem;"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card metric-card info h-100">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col">
                            <h6 class="text-uppercase text-muted mb-2 fw-semibold">
                                <i class="bi bi-arrow-repeat"></i> 今日转发
                            </h6>
                            <div class="metric-value text-info" id="todayForwards">
                                {today_total}
                            </div>
                            <div class="metric-change text-info" id="forwardsTrend">
                                <i class="bi bi-arrow-up"></i> 趋势良好
                            </div>
                        </div>
                        <div class="col-auto">
                            <div class="bg-info bg-opacity-10 p-3 rounded-circle">
                                <i class="bi bi-arrow-repeat text-info" style="font-size: 2rem;"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-xl-3 col-md-6 mb-4">
            <div class="card metric-card warning h-100">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col">
                            <h6 class="text-uppercase text-muted mb-2 fw-semibold">
                                <i class="bi bi-shield-check"></i> 去重缓存
                            </h6>
                            <div class="metric-value text-warning" id="dedupCache">
                                {dedup_cache_size}
                            </div>
                            <div class="metric-change text-muted" id="cacheInfo">
                                <i class="bi bi-database"></i> 缓存状态
                            </div>
                        </div>
                        <div class="col-auto">
                            <div class="bg-warning bg-opacity-10 p-3 rounded-circle">
                                <i class="bi bi-shield-check text-warning" style="font-size: 2rem;"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
        
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"stats_fragment error: {e}")
        return HTMLResponse(content="", status_code=500)
