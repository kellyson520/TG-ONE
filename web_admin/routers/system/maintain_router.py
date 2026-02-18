import os
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, Depends
from sqlalchemy import func, select

from core.config import settings
from web_admin.security.deps import admin_required, login_required
from web_admin.routers.settings_router import _get_full_settings_logic, _update_settings_logic
from services.backup_service import backup_service

from models.models import RuleLog, RuleStatistics, ChatStatistics, ErrorLog, MediaSignature, TaskQueue
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System Maintenance"])

@router.get("/config", response_model=ResponseSchema)
async def get_config(
    user = Depends(login_required),
    config_service = Depends(deps.get_config_service)
):
    """获取基础系统配置"""
    try:
        bot_token = settings.BOT_TOKEN
        api_id = settings.API_ID
        user_id = settings.USER_ID
        history_limit = await config_service.get('HISTORY_MESSAGE_LIMIT')
        
        try:
            history_limit = int(history_limit) if history_limit is not None else settings.HISTORY_MESSAGE_LIMIT
        except Exception:
            history_limit = settings.HISTORY_MESSAGE_LIMIT
        
        return ResponseSchema(success=True, data={
            'bot_token_set': bool(str(bot_token or '').strip()),
            'api_id_set': bool(str(api_id or '').strip()),
            'user_id_set': bool(str(user_id or '').strip()),
            'history_message_limit': history_limit,
        })
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.post("/config", response_model=ResponseSchema)
async def update_config(
    payload: Dict[str, Any], 
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service),
    settings_applier = Depends(deps.get_settings_applier)
):
    """更新基础系统配置 (主要是 HISTORY_MESSAGE_LIMIT)"""
    try:
        limit = int(payload.get('history_message_limit', 0))
        if limit < 0:
            limit = 0
            
        try:
            await config_service.set('HISTORY_MESSAGE_LIMIT', limit, data_type='integer')
            settings_applier.apply('HISTORY_MESSAGE_LIMIT', limit)
        except Exception as e:
            logger.error(f"Failed to update history limit: {e}")
            return ResponseSchema(success=False, error=str(e))
            
        return ResponseSchema(success=True, message='配置已更新', data={'history_message_limit': limit})

    except ValueError:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={'success': False, 'error': 'history_message_limit 必须为整数'}
        )
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={'success': False, 'error': str(e)}
        )

@router.get("/settings", response_model=ResponseSchema)
async def get_full_settings(
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service)
):
    """获取所有环境变量和设置元数据"""
    """获取所有环境变量和设置元数据"""
    return await _get_full_settings_logic(config_service)


@router.put("/settings", response_model=ResponseSchema)
async def update_settings(
    payload: Dict[str, Any], 
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service),
    settings_applier = Depends(deps.get_settings_applier)
):
    """批量更新系统设置项"""
    """批量更新系统设置项"""
    return await _update_settings_logic(payload, config_service)


@router.post("/restart", response_model=ResponseSchema)
async def restart_system(
    request: Request, 
    user = Depends(admin_required),
    guard_service = Depends(deps.get_guard_service)
):
    """重启系统服务"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在触发系统重启")
    
    try:
        loop = asyncio.get_event_loop()
        loop.call_later(1.0, guard_service.trigger_restart)
        logger.info(f"[Web-API] 用户 {user.username} 系统重启已触发，将在1秒后执行")
        return ResponseSchema(success=True, message='系统正在重启，请在 5-10 秒后刷新页面')
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 触发系统重启失败: {e}", exc_info=True)
        return ResponseSchema(success=False, error=str(e))

@router.post("/reload", response_model=ResponseSchema)
async def reload_config(request: Request, user = Depends(admin_required)):
    """重新加载动态配置 (不重启进程)"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在重新加载动态配置")
    
    try:
        from core.config_initializer import load_dynamic_config_from_db
        await load_dynamic_config_from_db(settings)
        logger.info(f"[Web-API] 用户 {user.username} 动态配置重新加载成功")
        return ResponseSchema(success=True, message='动态配置已重新加载')
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 重新加载动态配置失败: {e}", exc_info=True)
        return ResponseSchema(success=False, error=str(e))

@router.get("/backups", response_model=ResponseSchema)
async def list_backups(user = Depends(admin_required)):
    """获取所有系统备份 (代码 + 数据库)"""
    try:
        files = await backup_service.list_backups()
        return ResponseSchema(success=True, data=files)
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.post("/backups/trigger", response_model=ResponseSchema)
async def trigger_backup(user = Depends(admin_required)):
    """手动触发数据库备份"""
    try:
        path = await backup_service.backup_db()
        if path:
            return ResponseSchema(success=True, message=f'备份成功: {path.name}', data={'path': str(path)})
        else:
            return ResponseSchema(success=False, error='备份失败')
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.get("/archive-status", response_model=ResponseSchema)
async def get_archive_status(
    user = Depends(admin_required),
    manager = Depends(deps.get_archive_manager),
    db = Depends(deps.get_db)
):
    """获取数据归档状态统计"""
    try:
        stats = {}
        
        models = {
            "rule_logs": RuleLog,
            "rule_statistics": RuleStatistics,
            "chat_statistics": ChatStatistics,
            "error_logs": ErrorLog,
            "media_signatures": MediaSignature,
            "task_queue": TaskQueue
        }
        
        async with db.get_session() as session:
            for key, model in models.items():
                count_stmt = select(func.count()).select_from(model)
                res = await session.execute(count_stmt)
                stats[key] = res.scalar()
                
        # 归档配置
        config = {
            str(k.__tablename__): v for k, v in manager.archive_config.items()
        }
        
        return ResponseSchema(
            success=True,
            data={
                'sqlite_counts': stats,
                'archive_config': config,
                'is_running': manager.is_running
            }
        )
    except Exception as e:
        logger.error(f"Error fetching archive status: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.post("/archive/trigger", response_model=ResponseSchema)
async def trigger_archive(
    user = Depends(admin_required),
    manager = Depends(deps.get_archive_manager)
):
    """手动触发全量归档任务"""
    try:
        asyncio.create_task(manager.run_archiving_cycle())
        return ResponseSchema(success=True, message='归档任务已在后台启动')
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.get("/resources", response_model=ResponseSchema)
async def get_system_resources(user = Depends(login_required)):
    """获取系统资源使用情况 (CPU/Memory)"""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        return ResponseSchema(success=True, data={
            'cpu': cpu_percent,
            'memory': memory.percent,
            'memory_used': memory.used,
            'memory_total': memory.total
        })
    except ImportError:
        return ResponseSchema(success=True, data={'cpu': 0, 'memory': 0}, message="psutil module not installed")
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        return ResponseSchema(success=False, error=str(e))
