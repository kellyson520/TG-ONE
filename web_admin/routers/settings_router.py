
import os
import logging
import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path

from core.config import settings
from services.config_service import config_service
from services.settings_applier import settings_applier
from web_admin.security.deps import admin_required
from core.helpers.env_config import env_config_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("", response_class=JSONResponse)
async def get_settings_root(user = Depends(admin_required)):
    """获取所有环境变量和设置元数据"""
    return await _get_full_settings_logic()

@router.get("/meta", response_class=JSONResponse)
async def get_settings_meta(user = Depends(admin_required)):
    """获取设置元数据"""
    return await _get_full_settings_logic()

@router.put("", response_class=JSONResponse)
async def update_settings_root(payload: Dict[str, Any], user = Depends(admin_required)):
    """批量更新系统设置项"""
    return await _update_settings_logic(payload)

async def _get_full_settings_logic():
    try:
        # 生成设置元数据
        meta = [
            {'key':'HISTORY_MESSAGE_LIMIT','label':'历史消息限制','type':'integer','group':'通用','min':0,'max':100000,'requires_restart':False},
            {'key':'LOG_DIR','label':'日志目录','type':'string','group':'日志','requires_restart':True},
            {'key':'LOG_VIEW_MAX_BYTES','label':'在线查看最大字节','type':'integer','group':'日志','min':1024,'max':209715200,'requires_restart':False},
            {'key':'LOG_DOWNLOAD_MAX_BYTES','label':'下载最大字节','type':'integer','group':'日志','min':1024,'max':1073741824,'requires_restart':False},
            {'key':'FORWARD_RECORDER_DIR','label':'转发记录目录','type':'string','group':'转发记录','requires_restart':True},
            {'key':'RSS_SECRET_KEY','label':'RSS JWT秘钥','type':'string','group':'安全','sensitive':True,'requires_restart':True},
            {'key':'SECRET_KEY','label':'系统 JWT秘钥','type':'string','group':'安全','sensitive':True,'requires_restart':True},
            {'key':'WEB_ENABLED','label':'启用Web服务','type':'boolean','group':'Web','requires_restart':True}
        ]
        
        existing_keys = {item['key'] for item in meta}
        extra_keys = set(env_config_manager._config_cache.keys()) if hasattr(env_config_manager, '_config_cache') else set()
        
        allow_prefixes = (
            'WEB_', 'HEALTH_', 'LOG_', 'DB_', 'RSS_', 'FORWARD_', 'ARCHIVE_', 'AWS_', 'S3_', 'AI_',
            'API_', 'BOT_', 'UFB_', 'DUCKDB_', 'DEDUP_', 'VIDEO_', 'DEFAULT_', 'PROJECT_', 'PUSH_',
        )
        for k in os.environ.keys():
            if k.startswith(allow_prefixes):
                extra_keys.add(k)
        
        for k in sorted(extra_keys):
            if k in existing_keys:
                continue
            sensitive = bool(re.search(r'(SECRET|TOKEN|PASSWORD|KEY)$', k, re.I)) or ('PASSWORD' in k)
            meta.append({'key': k, 'label': k, 'type': 'string', 'group': '环境', 'sensitive': sensitive, 'requires_restart': True})
        
        items = {}
        # 预加载数据库配置以优化性能
        db_overrides = await config_service.get_all()

        for item in meta:
            k = item['key']
            v = None
            if k in db_overrides:
                 v = db_overrides[k]
            elif hasattr(settings, k):
                 v = getattr(settings, k)
            else:
                 v = config_service.get_sync(k)
                 
                 if v is None and hasattr(env_config_manager, '_config_cache'):
                     v = env_config_manager._config_cache.get(k)
            
            if isinstance(v, Path):
                v = str(v)

            item['value_present'] = bool(str(v).strip()) if v is not None else False
            
            if item.get('sensitive') and v:
                v = "********"
            items[k] = v
            
        return JSONResponse({'success': True, 'data': items, 'meta': meta})
    except Exception as e:
        logger.error(f"Error fetching full settings: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

async def _update_settings_logic(payload: Dict[str, Any]):
    try:
        restart_keys = {'LOG_DIR','FORWARD_RECORDER_DIR','RSS_SECRET_KEY','SECRET_KEY','WEB_ENABLED'}
        updated = {}
        
        for k, v in payload.items():
            dt = 'string'
            if k in {'HISTORY_MESSAGE_LIMIT','LOG_VIEW_MAX_BYTES','LOG_DOWNLOAD_MAX_BYTES'}:
                try:
                    v = int(v)
                    dt = 'integer'
                except Exception:
                    return JSONResponse({'success': False, 'error': f'{k} 必须为整数'}, status_code=400)
            
            if k in {'LOG_DIR','FORWARD_RECORDER_DIR','RSS_SECRET_KEY','SECRET_KEY'} and (not isinstance(v, str) or not str(v).strip()):
                return JSONResponse({'success': False, 'error': f'{k} 不能为空'}, status_code=400)
            
            await config_service.set(k, v, data_type=dt)
            try:
                env_config_manager.set_config(k, str(v), persist=True)
            except Exception:
                pass
            if k not in restart_keys:
                try:
                    settings_applier.apply(k, v)
                    logger.info(f"Applied setting change: {k} = {v}")
                except Exception as e:
                    logger.error(f"Failed to apply setting change: {k} = {v}: {e}")
            
            updated[k] = v
            logger.info(f"Updated setting: {k}")
            
        return JSONResponse({
            'success': True, 
            'data': {
                'updated': updated, 
                'requires_restart': any(k in restart_keys for k in payload.keys())
            }
        })
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)
