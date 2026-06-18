from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from starlette.responses import JSONResponse
import time
import logging
from collections import defaultdict, deque
import asyncio

from core.config import settings

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple In-Memory IP-based Rate Limiter.
    """
    # 最大追踪 IP 数量，超过时使用 LRU 淘汰
    MAX_TRACKED_IPS = 10000

    def __init__(self, app, max_requests: int = 300, window_seconds: int = 60, exclude_paths: list = None):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or ["/docs", "/openapi.json", "/favicon.ico", "/static", "/healthz"]
        self.request_history = defaultdict(deque)
        # LRU 顺序: 每次访问 IP 时更新，用于淘汰最久未活跃的 IP
        self._ip_access_order: deque = deque()
        self._cleanup_task = None

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        trusted_ips = settings.WEB_RATE_LIMIT_TRUSTED_IPS
        if isinstance(trusted_ips, str):
            trusted_ips = [item.strip() for item in trusted_ips.split(",") if item.strip()]

        if ip in trusted_ips:
            return await call_next(request)

        for p in self.exclude_paths:
            if path.startswith(p):
                return await call_next(request)

        now = time.time()
        history = self.request_history[ip]

        # LRU: 记录 IP 访问顺序
        self._ip_access_order.append(ip)
        # 如果追踪的 IP 数超过上限，淘汰最久未活跃的
        if len(self.request_history) > self.MAX_TRACKED_IPS:
            self._evict_stale_ips()
        
        # Lazy Cleanup for this IP
        while history and history[0] < now - self.window_seconds:
            history.popleft()
        
        if len(history) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP: {ip} on {path}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."}
            )
            
        history.append(now)
        
        # Auto-start cleanup loop if not running
        if not self._cleanup_task:
             self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

        return await call_next(request)

    async def _periodic_cleanup(self):
        """Clean up stale IPs every minute to prevent memory leaks."""
        while True:
            await asyncio.sleep(60)
            now = time.time()
            keys_to_delete = []
            for ip, history in self.request_history.items():
                # Cleanup deque
                while history and history[0] < now - self.window_seconds:
                    history.popleft()
                # If empty, mark for delete
                if not history:
                    keys_to_delete.append(ip)
            
            for key in keys_to_delete:
                del self.request_history[key]

    def _evict_stale_ips(self):
        """淘汰最久未活跃的 IP，保持 request_history 在合理大小"""
        target_size = int(self.MAX_TRACKED_IPS * 0.8)  # 淘汰到 80%
        while len(self.request_history) > target_size and self._ip_access_order:
            oldest_ip = self._ip_access_order.popleft()
            # 只淘汰没有正在进行请求的 IP
            if oldest_ip in self.request_history:
                history = self.request_history[oldest_ip]
                now = time.time()
                # 清理过期记录
                while history and history[0] < now - self.window_seconds:
                    history.popleft()
                # 如果该 IP 的记录已过期，删除
                if not history:
                    del self.request_history[oldest_ip]
