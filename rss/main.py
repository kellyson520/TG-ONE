from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from rss.app.routes.auth import router as auth_router
from rss.app.routes.rss import router as rss_router
from rss.app.api.endpoints import feed, subscription
import uvicorn
import logging
import sys
import os
from pathlib import Path
from utils.core.log_config import setup_logging
from utils.helpers.metrics import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, Counter, multiprocess, Gauge


@asynccontextmanager
async def lifespan(app: FastAPI):
    # RSS App 生命周期
    logger.info("RSS Panel 生命周期已启动")
    try:
        yield
    finally:
        logger.info("RSS Panel 生命周期已关闭")




root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))


# 获取日志记录器
logger = logging.getLogger(__name__)

app = FastAPI(title="TG Forwarder RSS", lifespan=lifespan)

# 注册路由
app.include_router(auth_router)
app.include_router(rss_router)
app.include_router(feed.router)
app.include_router(subscription.router)

# 模板配置
templates = Jinja2Templates(directory="rss/app/templates")

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """运行 RSS 服务器"""
    uvicorn.run(app, host=host, port=port)

# 添加直接运行支持
if __name__ == "__main__":
    # 只有在直接运行时才设置日志（而不是被导入时）
    setup_logging()
    run_server() 

# --- 健康检查与指标 ---
_REGISTRY = CollectorRegistry()
try:
    multiprocess.MultiProcessCollector(_REGISTRY)
except Exception:
    pass

RSS_HEALTH = Gauge('rss_health_status', 'RSS service health status', registry=_REGISTRY)
RSS_READY = Gauge('rss_ready_status', 'RSS service readiness status', registry=_REGISTRY)
RSS_HEALTH.set(1)
RSS_READY.set(1)

@app.get('/healthz')
def healthz():
    return {"status": "ok"}

@app.get('/readyz')
def readyz():
    return {"status": "ready"}

@app.get('/metrics')
def metrics():
    data = generate_latest(_REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)