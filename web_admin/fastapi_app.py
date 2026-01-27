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
from web_admin.routers.rules.rule_crud_router import router as rule_crud_router
from web_admin.routers.rules.rule_content_router import router as rule_content_router
from web_admin.routers.rules.rule_viz_router import router as rule_viz_router
from web_admin.routers.user_router import router as user_router
from web_admin.routers.user_router import router as user_router
from web_admin.routers.system.log_router import router as log_router
from web_admin.routers.system.maintain_router import router as maintain_router
from web_admin.routers.system.stats_router import router as stats_router
from web_admin.routers.websocket_router import router as websocket_router
from web_admin.routers.security_router import router as security_router
from web_admin.routers.simulator_router import router as simulator_router
from core.helpers.realtime_stats import realtime_stats_cache
from services.network.bot_heartbeat import get_heartbeat
from services.dedup.engine import smart_deduplicator
from core.helpers.forward_recorder import forward_recorder
# from core.helpers.env_config import env_config_manager
from web_admin.core.templates import templates, STATIC_DIR
from web_admin.routers.page_router import router as page_router
from web_admin.rss.routes.rss import router as rss_page_router
from web_admin.rss.api.endpoints.feed import router as rss_feed_router
from web_admin.rss.api.endpoints.subscription import router as rss_sub_router

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
app.include_router(rule_crud_router)
app.include_router(rule_content_router)
app.include_router(rule_viz_router)
app.include_router(user_router)
app.include_router(log_router)
app.include_router(maintain_router)
app.include_router(stats_router)
app.include_router(websocket_router)
app.include_router(security_router)
app.include_router(simulator_router)
app.include_router(page_router)
app.include_router(settings_router)

# RSS 模块路由
app.include_router(rss_page_router, prefix="/rss", tags=["RSS Pages"])
app.include_router(rss_feed_router, prefix="/api/rss/feed", tags=["RSS API"])
app.include_router(rss_sub_router, prefix="/api/rss/sub", tags=["RSS API"])

# RSS 模板路径挂载 (通过设置判断是否启用)
if settings.RSS_ENABLED:
    logger.info("✅ RSS Features enabled")

@app.exception_handler(PageRedirect)
async def page_redirect_handler(request: Request, exc: PageRedirect):
    return RedirectResponse(url=exc.url, status_code=302)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from core.context import trace_id_var
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
    """System readiness check for monitoring."""
    try:
        cfg_ready = bool(settings.BOT_TOKEN) and bool(settings.API_ID)
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


# Legacy routes removed.


# 统计路由已迁移至 web_admin/routers/stats_router.py (@router.get("/series"))

# 转发规则详情路由在 web_admin/routers/rule_router.py 中处理


# 导出 app 对象供外部使用
__all__ = ["app"]