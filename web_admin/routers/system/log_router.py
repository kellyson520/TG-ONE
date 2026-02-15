import logging
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO
import json

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, desc, func

from core.config import settings
from models.models import ErrorLog
from web_admin.security.deps import admin_required
from web_admin.schemas.response import ResponseSchema
from web_admin.api import deps

logger = logging.getLogger(__name__)

def _parse_audit_details(details: Optional[str]) -> str:
    if not details:
        return "-"
    try:
        data = json.loads(details)
        if isinstance(data, dict):
            reason = data.get("reason")
            if reason:
                mapping = {
                    "invalid_credentials": "凭据无效",
                    "account_locked": "账户已锁定",
                    "max_attempts_exceeded": "达到最大重试次数",
                    "invalid_otp": "动态验证码错误"
                }
                return mapping.get(reason, reason)
        return str(data)
    except:
        return details

router = APIRouter(prefix="/api/system", tags=["System Logs"])

@router.get("/logs/error_logs", response_model=ResponseSchema)
async def get_error_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    level: Optional[str] = None,
    module: Optional[str] = None,
    user = Depends(admin_required),
    db = Depends(deps.get_db)
):
    """从数据库获取结构化错误日志"""
    try:
        async with db.get_session() as session:
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
                    'message': log.message[:200] + '...' if log.message and len(log.message) > 200 else log.message,
                    'created_at': (f"{log.created_at}Z" if log.created_at and 'T' in log.created_at and not log.created_at.endswith('Z') else log.created_at),
                    'traceback': log.traceback[:300] + '...' if log.traceback and len(log.traceback) > 300 else log.traceback,
                    # Context usually small, but let's be safe
                    'context': str(log.context)[:500] + '...' if log.context and len(str(log.context)) > 500 else log.context
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
        logger.error(f"Error fetching error logs: {e}")
        return ResponseSchema(success=False, error=str(e))

@router.get("/logs/error_logs/{log_id}", response_model=ResponseSchema)
async def get_error_log_detail(
    log_id: int,
    user = Depends(admin_required),
    db = Depends(deps.get_db)
):
    """获取单条错误日志详情"""
    try:
        async with db.get_session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == log_id)
            result = await session.execute(stmt)
            log = result.scalar_one_or_none()
            
            if not log:
                return ResponseSchema(success=False, error="日志不存在")
                
            return ResponseSchema(
                success=True,
                data={
                    'id': log.id,
                    'level': log.level,
                    'module': log.module,
                    'function': log.function,
                    'message': log.message,
                    'created_at': (f"{log.created_at}Z" if log.created_at and 'T' in log.created_at and not log.created_at.endswith('Z') else log.created_at),
                    'traceback': log.traceback,
                    'context': log.context,
                    'rule_id': log.rule_id,
                    'chat_id': log.chat_id
                }
            )
    except Exception as e:
        logger.error(f"Error fetching log detail: {e}")
        return ResponseSchema(success=False, error=str(e))


@router.get("/logs/list", response_model=ResponseSchema)
async def list_logs(user = Depends(admin_required)):
    """列出日志目录下所有日志文件"""
    try:
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
        return ResponseSchema(success=True, data=files)
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

@router.get("/logs/view", response_model=ResponseSchema)
async def view_log(
    filename: str = Query(...), 
    user = Depends(admin_required),
    config_service = Depends(deps.get_config_service)
):
    """在线查看日志文件最后 N 字节"""
    try:
        # 安全性检查：防止路径穿越
        if "/" in filename or "\\" in filename or filename.startswith("."):
            return ResponseSchema(success=False, error='无效的文件名')
            
        log_path = Path(settings.LOG_DIR) / filename
        if not log_path.exists() or not log_path.is_file():
            return ResponseSchema(success=False, error='文件不存在')
            
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
            
        return ResponseSchema(
            success=True, 
            data={
                'filename': filename,
                'content': content,
                'truncated': file_size > read_size,
                'total_size': file_size
            }
        )
    except Exception as e:
        return ResponseSchema(success=False, error=str(e))

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
        from core.helpers.trace_analyzer import TraceAnalyzer
        
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

@router.get("/audit/logs", response_model=ResponseSchema)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    user = Depends(admin_required),
    audit_service = Depends(deps.get_audit_service)
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
                "details": _parse_audit_details(log.details),
                "status": log.status,
                "timestamp": log.timestamp.replace(tzinfo=timezone.utc).isoformat() if log.timestamp else None
            })

        return ResponseSchema(
            success=True,
            data={
                'logs': serialized_logs,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
        )
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Error fetching audit logs: {error_detail}")
        return ResponseSchema(success=False, error=str(e), meta={'traceback': error_detail})
