from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request
from services.access_control_service import access_control_service
from services.audit_service import audit_service
import logging
import asyncio

logger = logging.getLogger(__name__)

class IPGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/docs", "/openapi.json", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Skip checking for excluded paths (e.g., public webhooks or docs if desired)
        # Often /metrics or /health might also be excluded.
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        
        # Localhost is usually trusted, but maybe we want to guard it too?
        # For security, we should treat 127.0.0.1 same as others unless explicitly allow-listed in DB.
        # But to avoid locking oneself out during dev, maybe allow it?
        # Let's rely on DB rules purely. But logging out might be risky if whitelist enabled and 127.0.0.1 not in it.
        # Decision: Add explicit bypass for loopback if this is a local dev tool, but for a server it should be strict.
        # Given "TG ONE" sounds like a server bot, strict DB rules are safer. 
        # However, to prevent immediate lockout on first start if whitelist logic is buggy, 
        # check_ip_access returns TRUE by default if no whitelist exists.
        
        allowed = await access_control_service.check_ip_access(client_ip)
        
        if not allowed:
            logger.warning(f"Blocked access attempt from {client_ip} to {path}")
            
            # 记录审计日志 (异步，不阻塞响应)
            asyncio.create_task(
                audit_service.log_event(
                    action="IP_BLOCKED",
                    resource_type="IP_GUARD",
                    ip_address=client_ip,
                    user_agent=request.headers.get("user-agent", "unknown"),
                    details={"path": path, "method": request.method},
                    status="blocked"
                )
            )
            
            return JSONResponse(
                status_code=403,
                content={"detail": "Access Forbidden: IP not allowed"}
            )
            
        return await call_next(request)

