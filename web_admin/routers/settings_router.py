
import logging
import re
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pathlib import Path

from core.config import settings
from services.settings_applier import settings_applier
from web_admin.security.deps import admin_required
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("", response_model=ResponseSchema)
async def get_settings_root(
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service)
):
    """获取所有环境变量和设置元数据"""
    return await _get_full_settings_logic(config_service)

@router.get("/meta", response_model=ResponseSchema)
async def get_settings_meta(
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service)
):
    """获取设置元数据"""
    return await _get_full_settings_logic(config_service)

@router.put("", response_model=ResponseSchema)
async def update_settings_root(
    payload: Dict[str, Any], 
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service)
):
    """批量更新系统设置项"""
    return await _update_settings_logic(payload, config_service)

async def _get_full_settings_logic(config_service):
    try:
        # 定义核心设置的元数据（带分组和描述）
        # 这里的定义应与 Settings 类中的字段尽量对齐
        meta = [
            # 通用
            {'key':'HISTORY_MESSAGE_LIMIT','label':'历史消息限制','type':'integer','group':'通用','min':0,'max':100000,'requires_restart':False},
            {'key':'DEFAULT_TIMEZONE','label':'系统时区','type':'string','group':'通用','requires_restart':True},
            
            # 日志
            {'key':'LOG_LEVEL','label':'日志级别','type':'string','group':'日志','requires_restart':False},
            {'key':'LOG_DIR','label':'日志目录','type':'string','group':'日志','requires_restart':True},
            {'key':'LOG_FORMAT','label':'日志格式','type':'string','group':'日志','requires_restart':False},
            {'key':'LOG_VIEW_MAX_BYTES','label':'在线查看最大字节','type':'integer','group':'日志','min':1024,'max':209715200,'requires_restart':False},
            {'key':'LOG_DOWNLOAD_MAX_BYTES','label':'下载最大字节','type':'integer','group':'日志','min':1024,'max':1073741824,'requires_restart':False},
            
            # 数据库
            {'key':'DATABASE_URL','label':'数据库连接串','type':'string','group':'数据库','requires_restart':True, 'sensitive': True},
            {'key':'DB_POOL_SIZE','label':'连接池大小','type':'integer','group':'数据库','min':1,'max':1000,'requires_restart':True},
            
            # 转发记录
            {'key':'FORWARD_RECORDER_DIR','label':'转发记录目录','type':'string','group':'转发记录','requires_restart':True},
            {'key':'FORWARD_RECORDER_MODE','label':'记录模式','type':'string','group':'转发记录','requires_restart':False},
            
            # 安全
            {'key':'RSS_SECRET_KEY','label':'RSS JWT秘钥','type':'string','group':'安全','sensitive':True, 'requires_restart':True},
            {'key':'SECRET_KEY','label':'系统 JWT秘钥','type':'string','group':'安全','sensitive':True, 'requires_restart':True},
            {'key':'WEB_ADMIN_USERNAME','label':'管理员用户名','type':'string','group':'安全','requires_restart':False},
            {'key':'WEB_ADMIN_PASSWORD','label':'管理员密码','type':'string','group':'安全','sensitive':True, 'requires_restart':False},
            
            # Web
            {'key':'WEB_ENABLED','label':'启用Web服务','type':'boolean','group':'Web','requires_restart':True},
            {'key':'WEB_PORT','label':'Web服务端口','type':'integer','group':'Web','min':1,'max':65535,'requires_restart':True},
            {'key':'ALLOW_REGISTRATION','label':'允许用户注册','type':'boolean','group':'Web','requires_restart':False},

            # 运维
            {'key':'USERNAME','label':'OS 用户名 (权限修复用)','type':'string','group':'环境','requires_restart':False},
            {'key':'MIGRATE_BATCH_SIZE','label':'迁移批处理大小','type':'integer','group':'运维','requires_restart':False}
        ]
        
        existing_keys = {item['key'] for item in meta}
        
        # 允许展示的环境变量前缀
        allow_prefixes = (
            'WEB_', 'HEALTH_', 'LOG_', 'DB_', 'RSS_', 'FORWARD_', 'ARCHIVE_', 'AWS_', 'S3_', 'AI_',
            'API_', 'BOT_', 'UFB_', 'DUCKDB_', 'DEDUP_', 'VIDEO_', 'DEFAULT_', 'PROJECT_', 'PUSH_',
        )
        
        # 扫描所有配置项（仅限 Settings 类的字段）
        # 遵循 SSOT 原则：所有配置必须在 Settings 类中定义
        all_keys = set(existing_keys) | set(settings.model_fields.keys())

        # 补全元数据
        for k in sorted(all_keys):
            if k in existing_keys:
                continue
            sensitive = bool(re.search(r'(SECRET|TOKEN|PASSWORD|KEY)$', k, re.I)) or ('PASSWORD' in k)
            # 尝试从 Settings 字段描述中获取 Label
            label = k
            if k in settings.model_fields:
                field = settings.model_fields[k]
                if field.description:
                    label = field.description
            
            meta.append({
                'key': k, 
                'label': label, 
                'type': 'string', 
                'group': '其他项', 
                'sensitive': sensitive, 
                'requires_restart': True
            })
        
        items = {}
        # 预加载数据库配置
        db_overrides = await config_service.get_all()

        for item in meta:
            k = item['key']
            v = None
            if k in db_overrides:
                 v = db_overrides[k]
            elif hasattr(settings, k):
                 v = getattr(settings, k)
            
            # 类型校正 (针对前端展示)
            if isinstance(v, Path):
                v = str(v)

            item['value_present'] = bool(str(v).strip()) if v is not None else False
            
            # 脱敏处理
            if item.get('sensitive') and v:
                v = "********"
            items[k] = v
            
        return ResponseSchema(success=True, data=items, meta={'fields': meta})
    except Exception as e:
        logger.error(f"Error fetching full settings: {e}")
        return ResponseSchema(success=False, error=str(e))

async def _update_settings_logic(payload: Dict[str, Any], config_service):
    try:
        # 定义需要重启的配置项
        restart_keys = {
            'LOG_DIR', 'FORWARD_RECORDER_DIR', 'RSS_SECRET_KEY', 'SECRET_KEY', 
            'WEB_ENABLED', 'WEB_PORT', 'DATABASE_URL', 'DB_POOL_SIZE'
        }
        updated = {}
        
        for k, v in payload.items():
            dt = 'string'
            
            # 尝试根据 Settings 定义自动推断数据类型
            if k in settings.model_fields:
                field_type = settings.model_fields[k].annotation
                origin_type = getattr(field_type, '__origin__', field_type)
                
                if field_type == int or field_type == Optional[int]:
                    try:
                        v = int(v)
                        dt = 'integer'
                    except Exception:
                         return ResponseSchema(success=False, error=f'{k} 必须为整数')
                elif field_type == bool or field_type == Optional[bool]:
                    v = bool(v) if not isinstance(v, str) else v.lower() in ('true', '1', 'yes')
                    dt = 'boolean'
                elif field_type == float or field_type == Optional[float]:
                    try:
                        v = float(v)
                        dt = 'float'
                    except Exception:
                         return ResponseSchema(success=False, error=f'{k} 必须为数字')
                elif origin_type is list or (isinstance(field_type, type) and issubclass(field_type, list)) or 'List' in str(field_type):
                    # 处理列表 (支持 JSON 字符串或逗号分隔)
                    dt = 'list'
                    if isinstance(v, str):
                        try:
                            import json
                            v = json.loads(v)
                            if not isinstance(v, list):
                                v = [v]
                        except Exception:
                            v = [t.strip() for t in v.split(",") if t.strip()]

            # 必填项检查
            if k in {'LOG_DIR', 'FORWARD_RECORDER_DIR', 'RSS_SECRET_KEY', 'SECRET_KEY'} and (not str(v).strip()):
                return ResponseSchema(success=False, error=f'{k} 不能为空')
            
            # 1. 持久化到数据库
            await config_service.set(k, v, data_type=dt)
            
            # 2. 尝试热应用
            if k not in restart_keys:
                try:
                    settings_applier.apply(k, v)
                    logger.info(f"Applied setting change: {k} = {v}")
                except Exception as e:
                    logger.error(f"Failed to apply setting change: {k} = {v}: {e}")
            
            updated[k] = v
            
        return ResponseSchema(
            success=True, 
            data={
                'updated': updated, 
                'requires_restart': any(k in restart_keys for k in payload.keys())
            }
        )
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return ResponseSchema(success=False, error=str(e))
