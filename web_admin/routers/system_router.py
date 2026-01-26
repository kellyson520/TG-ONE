
import os
import logging
import asyncio
import traceback
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from datetime import datetime
from pathlib import Path

from core.config import settings
from services.config_service import config_service
from services.settings_applier import settings_applier
from services.system_service import guard_service
from services.audit_service import audit_service
from web_admin.security.deps import admin_required, login_required
from utils.core.env_config import env_config_manager
from repositories.archive_manager import get_archive_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/tasks", response_class=JSONResponse)
async def get_tasks_list(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    user = Depends(admin_required)
):
    """获取任务队列列表"""
    try:
        from core.container import container
        
        tasks, total = await container.task_repo.get_tasks(page, limit, status)
        
        data = []
        for t in tasks:
            data.append({
                'id': t.id,
                'type': t.task_type,
                'status': t.status,
                'priority': t.priority,
                'unique_key': t.unique_key,    # Expose unique_key (User asked for UUID display)
                'grouped_id': t.grouped_id,    # Expose grouped_id
                'retry_count': t.retry_count,
                'error_log': t.error_log,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'updated_at': t.updated_at.isoformat() if t.updated_at else None,
                'scheduled_at': t.scheduled_at.isoformat() if t.scheduled_at else None
            })
            
        return JSONResponse({
            'success': True,
            'data': {
                'items': data,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
        })
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/stats", response_class=JSONResponse)
async def get_system_stats(user = Depends(login_required)):
    """获取系统运行核心指标"""
    try:
        from core.container import container
        from services.forward_service import forward_service
        from services.dedup.engine import smart_deduplicator
        
        # 1. 规则统计
        total_rules = 0
        active_rules = 0
        try:
            rule_stats = await container.task_repo.get_rule_stats()
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
            dedup_stats = smart_deduplicator.get_stats()
            dedup_count = dedup_stats.get('cached_signatures', 0) + dedup_stats.get('cached_content_hashes', 0)
        except Exception:
            pass
            
        # 4. 系统运行状况 (容器管理)
        guard_stats = {}
        try:
            from services.system_service import guard_service
            guard_stats = guard_service.get_stats()
        except Exception:
            pass

        # 5. 趋势数据
        trend = []
        try:
            trend = await container.stats_repo.get_hourly_trend(24)
        except Exception:
            pass

        return JSONResponse({
            'success': True,
            'data': {
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
        })
    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/config", response_class=JSONResponse)
async def get_config(user = Depends(login_required)):
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
        
        return JSONResponse({'success': True, 'data': {
            'bot_token_set': bool(str(bot_token or '').strip()),
            'api_id_set': bool(str(api_id or '').strip()),
            'user_id_set': bool(str(user_id or '').strip()),
            'history_message_limit': history_limit,
        }})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/config", response_class=JSONResponse)
async def update_config(payload: Dict[str, Any], user = Depends(admin_required)):
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
            return JSONResponse({'success': False, 'error': '更新失败'}, status_code=500)
            
        return JSONResponse({'success': True, 'message': '配置已更新', 'data': {'history_message_limit': limit}})
    except ValueError:
        return JSONResponse({'success': False, 'error': 'history_message_limit 必须为整数'}, status_code=400)
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/settings", response_class=JSONResponse)
async def get_full_settings(user = Depends(admin_required)):
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
        
        import re
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
            # v = env_config_manager.get_config(k)
            # Replaced with direct settings/service access to avoid deprecation warnings
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
            
        return JSONResponse({'success': True, 'data': items, 'meta': meta})
    except Exception as e:
        logger.error(f"Error fetching full settings: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.put("/settings", response_class=JSONResponse)
async def update_settings(payload: Dict[str, Any], user = Depends(admin_required)):
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
                    return JSONResponse({'success': False, 'error': f'{k} 必须为整数'}, status_code=400)
            
            if k in {'LOG_DIR','FORWARD_RECORDER_DIR','RSS_SECRET_KEY'} and (not isinstance(v, str) or not str(v).strip()):
                return JSONResponse({'success': False, 'error': f'{k} 不能为空'}, status_code=400)
            
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
            
        return JSONResponse({
            'success': True, 
            'data': {
                'updated': updated, 
                'requires_restart': any(k in restart_keys for k in payload.keys())
            }
        })
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/restart", response_class=JSONResponse)
async def restart_system(request: Request, user = Depends(admin_required)):
    """重启系统服务"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在触发系统重启")
    
    try:
        loop = asyncio.get_event_loop()
        loop.call_later(1.0, guard_service.trigger_restart)
        logger.info(f"[Web-API] 用户 {user.username} 系统重启已触发，将在1秒后执行")
        return JSONResponse({'success': True, 'message': '系统正在重启，请在 5-10 秒后刷新页面'})
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 触发系统重启失败: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/reload", response_class=JSONResponse)
async def reload_config(request: Request, user = Depends(admin_required)):
    """重新加载动态配置 (不重启进程)"""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[Web-API] 用户 {user.username} ({client_ip}) 正在重新加载动态配置")
    
    try:
        from core.config_initializer import load_dynamic_config_from_db
        await load_dynamic_config_from_db(settings)
        logger.info(f"[Web-API] 用户 {user.username} 动态配置重新加载成功")
        return JSONResponse({'success': True, 'message': '动态配置已重新加载'})
    except Exception as e:
        logger.error(f"[Web-API] 用户 {user.username} 重新加载动态配置失败: {e}", exc_info=True)
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

# === 日志管理 ===

@router.get("/logs/error_logs", response_class=JSONResponse)
async def get_error_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    level: Optional[str] = None,
    module: Optional[str] = None,
    user = Depends(admin_required)
):
    """从数据库获取结构化错误日志"""
    try:
        from core.container import container
        from sqlalchemy import select, desc, func
        from models.models import ErrorLog
        
        async with container.db.session() as session:
            # 构建查询
            stmt = select(ErrorLog)
            conditions = []
            if level and level != 'ALL':
                conditions.append(ErrorLog.level == level)
            if module:
                conditions.append(ErrorLog.module.ilike(f"%{module}%"))
                
            if conditions:
                stmt = stmt.where(*conditions)
                
            # 计算总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0
            
            # 分页和排序
            stmt = stmt.order_by(desc(ErrorLog.created_at)).offset((page - 1) * limit).limit(limit)
            result = await session.execute(stmt)
            logs = result.scalars().all()
            
            data = []
            for log in logs:
                data.append({
                    'id': log.id,
                    'level': log.level,
                    'module': log.module,
                    'function': log.function,
                    'message': log.message,
                    'created_at': log.created_at,
                    'traceback': log.traceback,
                    'context': log.context
                })
                
            return JSONResponse({
                'success': True,
                'data': {
                    'items': data,
                    'total': total,
                    'page': page,
                    'limit': limit,
                    'total_pages': (total + limit - 1) // limit
                }
            })
    except Exception as e:
        logger.error(f"Error fetching error logs: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/logs/list", response_class=JSONResponse)
async def list_logs(user = Depends(admin_required)):
    """列出日志目录下所有日志文件"""
    try:
        # Use settings directly for LOG_DIR
        ld = getattr(settings, 'LOG_DIR', './logs')
        log_dir = Path(ld).absolute()
        
        files = []
        if log_dir.exists() and log_dir.is_dir():
            for f in log_dir.glob("*.log"):
                try:
                    stat = f.stat()
                except OSError:
                    continue
                files.append({
                    'name': f.name,
                    'size': stat.st_size,
                    'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            # 按修改时间逆序排序
            files.sort(key=lambda x: x['mtime'], reverse=True)
        return JSONResponse({'success': True, 'data': files})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/logs/view", response_class=JSONResponse)
async def view_log(filename: str = Query(...), user = Depends(admin_required)):
    """在线查看日志文件最后 N 字节"""
    try:
        # 安全性检查：防止路径穿越
        if "/" in filename or "\\" in filename or filename.startswith("."):
            return JSONResponse({'success': False, 'error': '无效的文件名'}, status_code=400)
            
        log_path = Path(settings.LOG_DIR) / filename
        if not log_path.exists() or not log_path.is_file():
            return JSONResponse({'success': False, 'error': '文件不存在'}, status_code=404)
            
        v_max = None
        if hasattr(settings, 'LOG_VIEW_MAX_BYTES'):
             v_max = getattr(settings, 'LOG_VIEW_MAX_BYTES')
        if v_max is None:
             v_max = await config_service.get('LOG_VIEW_MAX_BYTES')
        
        max_bytes = int(v_max) if v_max is not None else (1024 * 1024) # 默认 1MB
        file_size = log_path.stat().st_size
        
        # 读取末尾部分
        read_size = min(file_size, max_bytes)
        content = ""
        with open(log_path, 'rb') as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            content = f.read().decode('utf-8', errors='replace')
            
        return JSONResponse({
            'success': True, 
            'data': {
                'filename': filename,
                'content': content,
                'truncated': file_size > read_size,
                'total_size': file_size
            }
        })
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/logs/download")
async def download_log(filename: str = Query(...), user = Depends(admin_required)):
    """下载日志文件"""
    try:
        if "/" in filename or "\\" in filename or filename.startswith("."):
            raise HTTPException(status_code=400, detail="Invalid filename")
            
        log_path = Path(settings.LOG_DIR) / filename
        if not log_path.exists() or not log_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
            
        return FileResponse(
            path=log_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"Download log error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trace/download")
async def download_trace_report(
    trace_id: str = Query(..., min_length=4),
    format: str = Query("markdown", pattern="^(markdown|json|text)$"),
    user = Depends(admin_required)
):
    """
    下载指定 Trace ID 的分析报告
    """
    try:
        from utils.core.trace_analyzer import TraceAnalyzer
        from io import BytesIO, StringIO
        import json
        
        log_path = Path(settings.LOG_DIR) / "app.log"
        analyzer = TraceAnalyzer(str(log_path))
        events = analyzer.analyze(trace_id)
        
        if not events:
            raise HTTPException(status_code=404, detail="No events found for this Trace ID")
            
        # Generate content
        filename = f"trace_{trace_id}.{format}"
        content = ""
        media_type = "text/plain"
        
        if format == "markdown":
            content = analyzer.generate_markdown(trace_id, events)
            media_type = "text/markdown"
            filename = f"trace_{trace_id}.md"
        elif format == "json":
            def date_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return obj
            content = json.dumps(events, default=date_handler, indent=2, ensure_ascii=False)
            media_type = "application/json"
        else: # text
            lines = [f"{'TIME':<24} {'DELTA':<8} {'MODULE':<20} {'MESSAGE'}"]
            lines.append("-" * 80)
            start_time = events[0]["timestamp"]
            for event in events:
                delta_str = ""
                if event["timestamp"] and start_time:
                    delta = (event["timestamp"] - start_time).total_seconds() * 1000
                    delta_str = f"+{delta:.0f}ms"
                lines.append(f"{event['timestamp_str']:<24} {delta_str:<8} {event['module']:<20} {event['message']}")
            content = "\n".join(lines)
            
        # Stream response
        stream = BytesIO(content.encode('utf-8'))
        
        # Use StreamingResponse for in-memory file
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            stream, 
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trace download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === 备份管理 ===

@router.get("/backups", response_class=JSONResponse)
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
        return JSONResponse({'success': True, 'data': files})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/backups/trigger", response_class=JSONResponse)
async def trigger_backup(user = Depends(admin_required)):
    """手动触发数据库备份"""
    from repositories.backup import backup_database, rotate_backups
    try:
        path = backup_database()
        if path:
            rotate_backups()
            return JSONResponse({'success': True, 'message': f'备份成功: {os.path.basename(path)}', 'data': {'path': path}})
        else:
            return JSONResponse({'success': False, 'error': '备份失败'}, status_code=500)
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/audit/logs", response_class=JSONResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    user = Depends(admin_required)
):
    """获取系统审计日志"""
    try:
        logs, total = await audit_service.get_logs(page=page, limit=limit, user_id=user_id, action=action)
        
        # 序列化
        serialized_logs = []
        for log in logs:
            serialized_logs.append({
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "details": log.details,
                "status": log.status,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            })

        return JSONResponse({
            'success': True,
            'data': {
                'logs': serialized_logs,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Error fetching audit logs: {error_detail}")
        return JSONResponse({'success': False, 'error': str(e), 'traceback': error_detail}, status_code=500)


# === Phase H.1: 数据库连接池监控 ===

@router.get("/db-pool", response_class=JSONResponse)
async def get_db_pool_status(user = Depends(admin_required)):
    """
    获取数据库连接池状态
    
    Phase H.1: 数据库连接池优化
    """
    try:
        from models.models import get_async_engine
        
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
        
        return JSONResponse({
            'success': True,
            'data': {
                'pool': pool_status,
                'config': config,
                'database_url': str(engine.url).split('@')[-1] if '@' in str(engine.url) else str(engine.url)  # 隐藏密码
            }
        })
    except Exception as e:
        logger.error(f"Error fetching DB pool status: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)


# === Phase G.1: EventBus 统计 ===

@router.get("/eventbus/stats", response_class=JSONResponse)
async def get_eventbus_stats(user = Depends(admin_required)):
    """获取 EventBus 事件统计"""
    try:
        from core.container import container
        
        stats = container.bus.get_stats()
        return JSONResponse({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error fetching EventBus stats: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)


# === Phase G.2: 异常处理器统计 ===

@router.get("/exceptions/stats", response_class=JSONResponse)
async def get_exception_stats(user = Depends(admin_required)):
    """获取全局异常处理器统计"""
    try:
        from services.exception_handler import exception_handler
        
        stats = exception_handler.get_stats()
        return JSONResponse({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error fetching exception stats: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)


# === Phase G.3: WebSocket 统计 ===

@router.get("/websocket/stats", response_class=JSONResponse)
async def get_websocket_stats(user = Depends(login_required)):
    """获取 WebSocket 连接统计"""
    try:
        from web_admin.routers.websocket_router import ws_manager
        
        stats = ws_manager.get_stats()
        return JSONResponse({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error fetching WebSocket stats: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

# === Phase 3: Archive Management ===

@router.get("/archive-status", response_class=JSONResponse)
async def get_archive_status(user = Depends(admin_required)):
    """获取数据归档状态统计"""
    try:
        from sqlalchemy import func, select
        from models.models import RuleLog, RuleStatistics, ChatStatistics, ErrorLog, MediaSignature, TaskQueue
        from core.container import container
        
        manager = get_archive_manager()
        stats = {}
        
        models = {
            "rule_logs": RuleLog,
            "rule_statistics": RuleStatistics,
            "chat_statistics": ChatStatistics,
            "error_logs": ErrorLog,
            "media_signatures": MediaSignature,
            "task_queue": TaskQueue
        }
        
        async with container.db.session() as session:
            for key, model in models.items():
                count_stmt = select(func.count()).select_from(model)
                res = await session.execute(count_stmt)
                stats[key] = res.scalar()
                
        # 归档配置
        config = {
            str(k.__tablename__): v for k, v in manager.archive_config.items()
        }
        
        return JSONResponse({
            'success': True,
            'data': {
                'sqlite_counts': stats,
                'archive_config': config,
                'is_running': manager.is_running
            }
        })
    except Exception as e:
        logger.error(f"Error fetching archive status: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/archive/trigger", response_class=JSONResponse)
async def trigger_archive(user = Depends(admin_required)):
    """手动触发全量归档任务"""
    try:
        manager = get_archive_manager()
        asyncio.create_task(manager.run_archiving_cycle())
        return JSONResponse({'success': True, 'message': '归档任务已在后台启动'})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/stats_fragment", response_class=HTMLResponse)
async def api_stats_fragment(request: Request, user = Depends(login_required)):
    """获取统计片段（用于HTMX更新）"""
    try:
        # 在函数内部导入，避免循环依赖
        from services.forward_service import forward_service
        from core.container import container
        
        # 获取统计数据
        total_rules = 0
        active_rules = 0
        today_total = 0
        dedup_cache_size = 0
        
        # 获取规则统计
        try:
            # ✅ 调用 Repository，逻辑收敛
            rule_stats = await container.task_repo.get_rule_stats()
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
            from services.dedup.engine import smart_deduplicator
            dedup_stats = smart_deduplicator.get_stats()
            dedup_cache_size = dedup_stats.get('cached_signatures', 0) + dedup_stats.get('cached_content_hashes', 0)
        except Exception:
            pass
        
        # 计算活跃规则百分比
        active_percentage = 0
        if total_rules > 0:
            active_percentage = round((active_rules / total_rules) * 100)
        
        # 构建HTML响应 - 保持与 dashboard.html 内部结构一致，但作为独立片段
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
