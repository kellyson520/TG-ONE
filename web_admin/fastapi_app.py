import os
import sys
import logging

# 锁定入口：禁止直接运行此文件，必须通过 main.py 启动
if __name__ == "__main__":
    print("ERROR: This file cannot be run directly.")
    print("Please start the application through main.py instead.")
    sys.exit(1)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, Query
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyCookie
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import jwt
import requests
import hashlib
import asyncio
import traceback


# JWT 配置 - 已迁移至 core.config.settings
# 设置日志
logger = logging.getLogger(__name__)

# 导入内部模块
from core.config import settings
from models.models import User, get_db_health, ForwardRule, Chat
from core.container import container
from services.config_service import config_service
from services.settings_applier import settings_applier
from services.rule_service import RuleQueryService
from services.authentication_service import authentication_service
from services.system_service import system_service
from web_admin.routers.auth_router import router as auth_router
from web_admin.routers.rule_router import router as rule_router
from web_admin.routers.user_router import router as user_router
from web_admin.routers.system_router import router as system_router
from web_admin.routers.stats_router import router as stats_router
from web_admin.routers.websocket_router import router as websocket_router
from web_admin.routers.security_router import router as security_router
from web_admin.routers.simulator_router import router as simulator_router
from utils.helpers.realtime_stats import realtime_stats_cache
from utils.network.bot_heartbeat import get_heartbeat
from utils.processing.smart_dedup import smart_deduplicator
from utils.forward_recorder import forward_recorder
# from utils.core.env_config import env_config_manager
from web_admin.core.templates import templates, STATIC_DIR
from web_admin.routers.page_router import router as page_router

# 安全模块导入 (Phase 1 Security Enhancement)
from services.audit_service import audit_service
from web_admin.security.csrf import CSRFMiddleware, validate_csrf, csrf_token_input
from web_admin.middlewares.ip_guard_middleware import IPGuardMiddleware
from web_admin.routers.settings_router import router as settings_router
from web_admin.security.exceptions import PageRedirect
from web_admin.middlewares.trace_middleware import TraceMiddleware

# 模板和静态文件路径配置
# 模板和静态文件路径配置 (Refactored to web_admin.core.templates)
# BASE_DIR, TEMPLATES_DIR, STATIC_DIR moved to core.templates

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 安装 WebSocket 日志处理器
    try:
        from web_admin.security.log_broadcast_handler import install_websocket_log_handler
        install_websocket_log_handler()
        logger.info("WebSocket 日志推送已启用")
    except Exception as e:
        logger.error(f"无法启动 WebSocket 日志推送: {e}")
        
    logger.info("Web Admin API 已启动")
    try:
        yield
    except asyncio.CancelledError:
        logger.warning("Web Admin API 生命周期中断 (Cancelled)")
        raise
    except BaseException as e:
        if not isinstance(e, GeneratorExit):
            logger.error(f"Web Admin API 生命周期异常: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Web Admin API 已关闭")

from fastapi.exceptions import RequestValidationError

# 创建 FastAPI 应用
app = FastAPI(
    title="Telegram Forwarder Admin",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None
)

# 注册路由
app.include_router(auth_router)
app.include_router(rule_router)
app.include_router(user_router)
app.include_router(system_router)
app.include_router(stats_router)
app.include_router(websocket_router)
app.include_router(security_router)
app.include_router(simulator_router)
app.include_router(page_router)
app.include_router(settings_router)

# [Refactor Fix] 统一挂载 RSS 面板
if settings.RSS_ENABLED:
    try:
        from rss.main import app as rss_app
        app.mount("/rss", rss_app)
        logger.info("✅ RSS Panel mounted at /rss")
    except ImportError as e:
        logger.warning(f"⚠️ RSS Panel mounting failed: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error during RSS mounting: {e}")

@app.exception_handler(PageRedirect)
async def page_redirect_handler(request: Request, exc: PageRedirect):
    return RedirectResponse(url=exc.url, status_code=302)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from utils.core.log_config import trace_id_var
    trace_id = trace_id_var.get()
    
    # 记录详细错误
    logger.error(f"Uncaught Exception: {str(exc)} [TraceID: {trace_id}]", exc_info=True)
    
    # 根据请求类型返回
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                "message": str(exc) if settings.DEBUG else "服务器内部错误，请联系管理员",
                "trace_id": trace_id
            }
        )
    
    # 页面请求
    return HTMLResponse(
        content=f"<html><body><h1>500 Internal Server Error</h1><p>Trace ID: {trace_id}</p></body></html>",
        status_code=500
    )

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trace ID 追踪 (最外层，确保捕获所有逻辑)
app.add_middleware(TraceMiddleware)

# CSRF 防护 (Phase 2)
app.add_middleware(CSRFMiddleware)

# IP 访问控制 (Phase 3)
# 注意：最后添加的中间件最先执行。IP检查应在CSRF和鉴权之前。
app.add_middleware(IPGuardMiddleware)

# 挂载静态文件
# 挂载静态文件
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    logger.warning(f"静态文件目录不存在: {STATIC_DIR}")

# 模板引擎配置已迁移至 web_admin.core.templates



# 辅助函数
def _issue_token(user_id: int) -> str:
    """生成 JWT 访问令牌 (兼容性)"""
    from datetime import datetime, timedelta
    import jwt
    
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": str(user_id), "exp": expire, "type": "access"}
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# 鉴权依赖
def _get_allow_registration():
    return system_service.get_allow_registration()

def _set_allow_registration(v: bool):
    system_service.set_allow_registration(v)

# 鉴权依赖
from web_admin.security.deps import get_current_user, login_required, admin_required

# 健康检查路由
@app.get("/healthz")
async def healthz():
    db = {}
    try:
        db = get_db_health()
    except Exception:
        db = {}
    sys_stats = {}
    try:
        sys_stats = await realtime_stats_cache.get_system_stats()
    except Exception:
        sys_stats = {}
    return JSONResponse({'status': 'ok', 'db_connected': bool((db or {}).get('connected')), 'system': sys_stats})

@app.get("/readyz")
async def readyz():
    try:
        bt = settings.BOT_TOKEN
        api_id = settings.API_ID
        user_id = 0 # Not strictly required in settings as int, usually loaded from session strings or similar.
        # But settings model has API_ID (int?)
        # Let's check core/config.py again. API_ID is Optional[int].
        # In readyz logic: 
        # api_id = env_config_manager.get_config('API_ID') -> str
        # user_id = env_config_manager.get_config('USER_ID') -> str. 
        # settings might not have USER_ID field? 
        # Check core/config.py -> no USER_ID field.
        # The env_config_manager reads env variables. USER_ID might be in env but not in Settings model?
        # If so, I should fallback to os.getenv or env_config_manager for USER_ID if it's not in settings.
        # However, usage of env_config_manager.get_config is deprecated.
        # If I look at lines 175-177 in original:
        # bt = ...get_config('BOT_TOKEN')
        # api_id = ...('API_ID')
        # user_id = ...('USER_ID')
        # I should use os.getenv for USER_ID if it's just an env var not in settings.
        
        # Let's use:
        bt = settings.BOT_TOKEN
        api_id = settings.API_ID
        user_id = os.getenv('USER_ID')
        
        cfg_ready = bool(str(bt or '').strip()) and bool(str(api_id or '').strip())
        # Removing user_id check requirement if it's not core setting, or check if it exists.
        if user_id:
             cfg_ready = cfg_ready and bool(str(user_id).strip())
             
    except Exception:
        cfg_ready = False
    db_ok = False
    try:
        db_ok = bool(get_db_health().get('connected'))
    except Exception:
        db_ok = False
    st = 'ready' if (cfg_ready and db_ok) else 'not_ready'
    return JSONResponse({'status': st, 'config_ready': cfg_ready, 'db_connected': db_ok})

@app.get("/metrics")
async def metrics():
    cpu = 0.0
    mem = 0.0
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.05)
        mem = psutil.virtual_memory().percent
    except Exception:
        pass
    text = []
    text.append('web_admin_up 1')
    text.append(f'web_admin_cpu_percent {cpu}')
    text.append(f'web_admin_memory_percent {mem}')
    return "\n".join(text), 200, {'Content-Type': 'text/plain; version=0.0.4'}



# Archive view moved to page_router

# Duplicate rule routes removed. Usage delegated to web_admin.routers.rule_router.


# 聊天相关路由
@app.get("/api/chats", response_class=JSONResponse)
async def api_get_chats(request: Request, user = Depends(login_required)):
    """返回聊天列表用于过滤"""
    try:
        # ✅ 调用 Repository，逻辑收敛
        chats = await container.rule_repo.get_all_chats()
        items = []
        for c in chats:
            items.append({
                'id': c.id,
                'title': getattr(c, 'name', None),
                'username': getattr(c, 'username', None),
                'telegram_chat_id': c.telegram_chat_id,
                'chat_type': c.chat_type,
                'member_count': c.member_count
            })
        return JSONResponse({'success': True, 'data': items})
    except Exception as e:
        logger.error(f"获取聊天列表失败: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

# 可视化路由
@app.get("/api/visualization/graph", response_class=JSONResponse)
async def api_visualization_graph(request: Request, user = Depends(login_required)):
    """返回规则-聊天图谱数据"""
    try:
        # ✅ 调用 Repository，逻辑收敛
        rules = await container.rule_repo.get_all_rules_with_chats()
        chats = await container.rule_repo.get_all_chats()
        nodes = []
        edges = []
        chat_map = {}
        for chat in chats:
            node_id = f"chat_{chat.id}"
            chat_map[chat.id] = node_id
            nodes.append({
                'id': node_id,
                'label': getattr(chat, 'name', None) or f"Chat_{chat.telegram_chat_id}",
                'type': 'chat',
                'data': {
                    'telegram_chat_id': chat.telegram_chat_id,
                    'username': getattr(chat, 'username', None),
                    'chat_type': chat.chat_type,
                    'member_count': chat.member_count
                }
            })
        for rule in rules:
            rule_node_id = f"rule_{rule.id}"
            nodes.append({
                'id': rule_node_id,
                'label': f"规则 {rule.id}",
                'type': 'rule',
                'data': {
                    'enabled': rule.enable_rule,
                    'enable_dedup': rule.enable_dedup,
                    'keywords_count': len(rule.keywords) if rule.keywords else 0,
                    'replace_rules_count': len(rule.replace_rules) if rule.replace_rules else 0
                }
            })
            if rule.source_chat_id and rule.source_chat_id in chat_map:
                edges.append({
                    'id': f"edge_src_{rule.id}",
                    'source': chat_map[rule.source_chat_id],
                    'target': rule_node_id,
                    'type': 'source',
                    'label': ''
                })
            if rule.target_chat_id and rule.target_chat_id in chat_map:
                edges.append({
                    'id': f"edge_tgt_{rule.id}",
                    'source': rule_node_id,
                    'target': chat_map[rule.target_chat_id],
                    'type': 'target',
                    'label': ''
                })
        graph_data = {'nodes': nodes, 'edges': edges}
        return JSONResponse({'success': True, 'data': graph_data})
    except Exception as e:
        logger.error(f"获取可视化图谱数据失败: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)}), 500

# 规则开关路由
@app.post("/api/rules/{rule_id}/toggle", response_class=JSONResponse)
async def api_toggle_rule(request: Request, rule_id: int, user = Depends(admin_required)):
    try:
        # ✅ 调用 Repository，逻辑收敛
        new_state = await container.rule_repo.toggle_rule(rule_id)
        if new_state is None:
            return JSONResponse({'success': False, 'error': 'Rule not found'}, status_code=404)
        return JSONResponse({'success': True, 'data': {'enabled': new_state}})
    except Exception as e:
        logger.error(f"切换规则状态失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

# 错误日志相关路由
@app.get("/api/error_logs", response_class=JSONResponse)
async def api_get_error_logs(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    level: str = Query(None),
    user = Depends(admin_required)
):
    """获取系统错误日志"""
    try:
        # ✅ 调用 Repository，逻辑收敛
        items, total = await container.stats_repo.get_error_logs(page, size, level)
        
        data = []
        for item in items:
            data.append({
                'id': item.id,
                'level': getattr(item, 'level', 'ERROR'),
                'module': getattr(item, 'module', ''),
                'message': getattr(item, 'message', ''),
                'created_at': item.created_at.isoformat() if item.created_at else None
            })
        
        return JSONResponse({'success': True, 'data': {'total': total, 'items': data}})
    except Exception as e:
        logger.error(f"获取错误日志失败: {e}")
        return JSONResponse({'success': False, 'error': str(e)}), 500

@app.get("/api/logs/files", response_class=JSONResponse)
async def api_list_log_files(request: Request, user = Depends(admin_required)):
    """获取日志文件列表"""
    try:
        log_files = []
        log_dir = settings.LOG_DIR
        
        if not log_dir.exists():
             return JSONResponse({'success': True, 'data': []})

        # 获取日志目录下的.log文件
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                try:
                    full_path = log_dir / file
                    stat = full_path.stat()
                    log_files.append({
                        'name': file,
                        'size': stat.st_size,
                        'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception:
                    pass
        
        # 按修改时间倒序排列
        log_files.sort(key=lambda x: x['mtime'], reverse=True)
        return JSONResponse({'success': True, 'data': log_files})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}), 500

@app.get("/api/logs/tail", response_class=JSONResponse)
async def api_tail_log(
    request: Request,
    file: str = Query(...),
    lines: int = Query(100, ge=1, le=1000),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    level: str = Query(None),
    q: str = Query(None),
    user = Depends(admin_required)
):
    """读取日志文件末尾"""
    try:
        # 安全检查
        if not file.endswith('.log') or '/' in file or '\\' in file:
            return JSONResponse({'success': False, 'error': '无效的文件名'}), 400
        
        log_dir = settings.LOG_DIR
        file_path = log_dir / file
        
        if not file_path.exists():
            return JSONResponse({'success': False, 'error': '文件不存在'}), 404
            
        # 使用limit覆盖lines参数（兼容前端）
        actual_lines = limit
        content = []
        try:
            # 简单的读取实现，生产环境可能需要更高效的实现
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 读取最后N行
                file_size = file_path.stat().st_size
                read_size = min(file_size, 1024 * 1024) # 最多读1MB
                if file_size > read_size:
                    f.seek(file_size - read_size)
                
                lines_data = f.readlines()
                content = lines_data[-actual_lines:]
        except Exception as e:
            return JSONResponse({'success': False, 'error': f"读取文件失败: {e}"}), 500
        
        # 应用搜索和级别筛选
        filtered_content = content
        if q:
            filtered_content = [line for line in filtered_content if q.lower() in line.lower()]
        if level:
            filtered_content = [line for line in filtered_content if level.upper() in line]
        
        # 应用offset（当前实现中offset无实际作用，因为我们只读取了最后actual_lines行）
        
        # 返回与前端期望一致的数据格式
        return JSONResponse({'success': True, 'data': {'items': filtered_content}})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}), 500

@app.get("/api/logs/download")
async def api_download_log(request: Request, file: str = Query(...), user = Depends(admin_required)):
    """下载日志文件"""
    # 安全检查
    if not file.endswith('.log') or '/' in file or '\\' in file:
        return JSONResponse({'success': False, 'error': '无效的文件名'}), 400
    
    log_dir = settings.LOG_DIR
    file_path = log_dir / file
    
    if not file_path.exists():
        return JSONResponse({'success': False, 'error': '文件不存在'}), 404
        
    return FileResponse(file_path, filename=file)


# 统计路由已迁移至 web_admin/routers/stats_router.py (@router.get("/series"))

# 转发规则详情路由在 web_admin/routers/rule_router.py 中处理


# 导出 app 对象供外部使用
__all__ = ["app"]