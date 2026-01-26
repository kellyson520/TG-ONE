import os
import logging
import asyncio
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
import re

from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy import func, select

from core.config import settings
from web_admin.security.deps import admin_required, login_required
from utils.core.env_config import env_config_manager
from repositories.backup import backup_database, rotate_backups
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
        user_id = os.getenv('USER_ID')
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
    config_service = Depends(deps.get_config_service)
):
    """更新基础系统配置 (主要是 HISTORY_MESSAGE_LIMIT)"""
    try:
        limit = int(payload.get('history_message_limit', 0))
        if limit < 0:
            limit = 0
            
        ok = env_config_manager.set_history_message_limit(limit)
        try:
            await config_service.set('HISTORY_MESSAGE_LIMIT', limit, data_type='integer')
        except Exception:
            pass
            
        if not ok:
            return ResponseSchema(success=False, error='更新失败')
            
        return ResponseSchema(success=True, message='配置已更新', data={'history_message_limit': limit})
    except ValueError:
        return ResponseSchema(success=False, error='history_message_limit 必须为整数')
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.get("/settings", response_model=ResponseSchema)
async def get_full_settings(
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service)
):
    """获取所有环境变量和设置元数据"""
    try:
        # 生成设置元数据
        meta = [
            {'key':'HISTORY_MESSAGE_LIMIT','label':'历史消息限制','type':'integer','group':'通用','min':0,'max':100000,'requires_restart':False},
            {'key':'LOG_DIR','label':'日志目录','type':'string','group':'日志','requires_restart':True},
            {'key':'LOG_VIEW_MAX_BYTES','label':'在线查看最大字节','type':'integer','group':'日志','min':1024,'max':209715200,'requires_restart':False},
            {'key':'LOG_DOWNLOAD_MAX_BYTES','label':'下载最大字节','type':'integer','group':'日志','min':1024,'max':1073741824,'requires_restart':False},
            {'key':'FORWARD_RECORDER_DIR','label':'转发记录目录','type':'string','group':'转发记录','requires_restart':True},
            {'key':'RSS_SECRET_KEY','label':'JWT秘钥','type':'string','group':'安全','sensitive':True,'requires_restart':True},
            {'key':'WEB_ENABLED','label':'启用Web服务','type':'boolean','group':'Web','requires_restart':True},
            {'key':'ALLOW_REGISTRATION','label':'允许新用户注册','type':'boolean','group':'安全','requires_restart':False}
        ]
        
        existing_keys = {item['key'] for item in meta}
        extra_keys = set(env_config_manager._config_cache.keys()) if hasattr(env_config_manager, '_config_cache') else set()
        
        allow_prefixes = (
            'WEB_', 'HEALTH_', 'LOG_', 'DB_', 'RSS_', 'FORWARD_', 'ARCHIVE_', 'AWS_', 'S3_', 'AI_',
            'API_', 'BOT_', 'UFB_', 'DUCKDB_', 'DEDUP_', 'VIDEO_', 'DEFAULT_', 'PROJECT_', 'PUSH_',
        )
        if os.environ.get('ENV') != 'PROD':  # Limit env dump in non-prod unless needed
             allow_prefixes = allow_prefixes
        for k in os.environ.keys():
            if k.startswith(allow_prefixes):
                extra_keys.add(k)
        
        for k in sorted(extra_keys):
            if k in existing_keys:
                continue
            sensitive = bool(re.search(r'(SECRET|TOKEN|PASSWORD|KEY)$', k, re.I)) or ('PASSWORD' in k)
            meta.append({'key': k, 'label': k, 'type': 'string', 'group': '环境', 'sensitive': sensitive, 'requires_restart': True})
        
        items = {}
        for item in meta:
            k = item['key']
            # Check DB/Service first (Async)
            v = await config_service.get(k)
            
            # Fallback to Settings object (Env/Defaults)
            if v is None:
                if hasattr(settings, k):
                    v = getattr(settings, k)
                else:
                    v = os.getenv(k)
                    if v is None and hasattr(env_config_manager, '_config_cache'):
                         v = env_config_manager._config_cache.get(k)
            item['value_present'] = bool(str(v).strip()) if v is not None else False
            
            # 敏感值脱敏
            if item.get('sensitive') and v:
                v = "********"
            items[k] = v
            
        return ResponseSchema(success=True, data=items, meta={'fields': meta})
    except Exception as e:
        logger.error(f"Error fetching full settings: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.put("/settings", response_model=ResponseSchema)
async def update_settings(
    payload: Dict[str, Any], 
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service),
    settings_applier = Depends(deps.get_settings_applier)
):
    """批量更新系统设置项"""
    try:
        restart_keys = {'LOG_DIR','FORWARD_RECORDER_DIR','RSS_SECRET_KEY','WEB_ENABLED'}
        updated = {}
        
        for k, v in payload.items():
            dt = 'string'
            if k in {'HISTORY_MESSAGE_LIMIT','LOG_VIEW_MAX_BYTES','LOG_DOWNLOAD_MAX_BYTES'}:
                try:
                    v = int(v)
                    dt = 'integer'
                except Exception:
                    return ResponseSchema(success=False, error=f'{k} 必须为整数')
            
            if k in {'LOG_DIR','FORWARD_RECORDER_DIR','RSS_SECRET_KEY'} and (not isinstance(v, str) or not str(v).strip()):
                return ResponseSchema(success=False, error=f'{k} 不能为空')
            
            # 1. 写入数据库配置服务 (持久化)
            await config_service.set(k, v, data_type=dt)
            # 2. 写入 .env 文件
            try:
                env_config_manager.set_config(k, str(v), persist=True)
            except Exception:
                pass
            # 3. 尝试热应用 (如果不要求重启)
            if k not in restart_keys:
                try:
                    settings_applier.apply(k, v)
                except Exception:
                    pass
            
            updated[k] = v
            
        return ResponseSchema(
            success=True, 
            data={
                'updated': updated, 
                'requires_restart': any(k in restart_keys for k in payload.keys())
            }
        )
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

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
    """获取所有数据库备份"""
    try:
        backup_dir = Path(os.environ.get("BACKUP_DIR", "./backups"))
        files = []
        if backup_dir.exists() and backup_dir.is_dir():
            for f in backup_dir.glob("*.bak"):
                stat = f.stat()
                files.append({
                    'name': f.name,
                    'size': stat.st_size,
                    'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            files.sort(key=lambda x: x['mtime'], reverse=True)
        return ResponseSchema(success=True, data=files)
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.post("/backups/trigger", response_model=ResponseSchema)
async def trigger_backup(user = Depends(admin_required)):
    """手动触发数据库备份"""
    try:
        path = backup_database()
        if path:
            rotate_backups()
            return ResponseSchema(success=True, message=f'备份成功: {os.path.basename(path)}', data={'path': path})
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
        
        async with db.session() as session:
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
