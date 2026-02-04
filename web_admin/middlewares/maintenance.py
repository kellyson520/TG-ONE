"""
维护模式中间件 (Maintenance Mode Middleware)
在系统升级期间拦截请求，返回 503 状态
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, HTMLResponse
from pathlib import Path

# 锁文件路径
LOCK_FILE = Path("/app/data/UPDATE_LOCK.json")

class MaintenanceMiddleware(BaseHTTPMiddleware):
    """
    维护模式中间件
    
    当检测到 UPDATE_LOCK.json 文件存在时，说明系统正在升级或刚刚启动正在迁移DB
    此时拦截所有请求，返回 503 状态
    """
    
    async def dispatch(self, request, call_next):
        # 如果锁文件存在，说明系统正在升级或刚刚启动正在迁移DB
        if LOCK_FILE.exists():
            # 放行静态资源，否则维护页面也加载不出来
            if request.url.path.startswith("/static") or request.url.path.startswith("/favicon"):
                return await call_next(request)
            
            # API 请求返回 503 JSON
            if request.url.path.startswith("/api"):
                return JSONResponse(
                    status_code=503,
                    content={
                        "code": "SYSTEM_UPDATING", 
                        "message": "System is updating. Please retry in 30 seconds."
                    }
                )
            
            # 页面请求返回维护页面
            maintenance_html = """
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>系统维护中</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        color: #fff;
                    }
                    .container {
                        text-align: center;
                        padding: 40px;
                        background: rgba(255, 255, 255, 0.1);
                        backdrop-filter: blur(10px);
                        border-radius: 20px;
                        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                    }
                    h1 {
                        font-size: 48px;
                        margin: 0 0 20px 0;
                        animation: pulse 2s ease-in-out infinite;
                    }
                    p {
                        font-size: 18px;
                        margin: 10px 0;
                        opacity: 0.9;
                    }
                    .spinner {
                        border: 4px solid rgba(255, 255, 255, 0.3);
                        border-top: 4px solid #fff;
                        border-radius: 50%;
                        width: 50px;
                        height: 50px;
                        animation: spin 1s linear infinite;
                        margin: 30px auto;
                    }
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.7; }
                    }
                </style>
                <script>
                    // 每 5 秒自动刷新页面
                    setTimeout(() => {
                        window.location.reload();
                    }, 5000);
                </script>
            </head>
            <body>
                <div class="container">
                    <h1>🔧 系统升级中</h1>
                    <div class="spinner"></div>
                    <p>系统正在进行自动升级，请稍候...</p>
                    <p>页面将在 5 秒后自动刷新</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(
                content=maintenance_html,
                status_code=503
            )
            
        return await call_next(request)
