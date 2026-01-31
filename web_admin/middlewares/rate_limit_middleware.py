from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from starlette.responses import JSONResponse
import time
import logging
from collections import defaultdict, deque
import asyncio

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple In-Memory IP-based Rate Limiter.
    """
    def __init__(self, app, max_requests: int = 300, window_seconds: int = 60, exclude_paths: list = None):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or ["/docs", "/openapi.json", "/favicon.ico", "/static", "/healthz"]
        self.request_history = defaultdict(deque)
        self._cleanup_task = None

    async def dispatch(self, request: Request, call_next):
        # Allow loopback for dev
        ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if ip in ["127.0.0.1", "localhost", "::1"]:
            return await call_next(request)

        for p in self.exclude_paths:
            if path.startswith(p):
                return await call_next(request)

        now = time.time()
        history = self.request_history[ip]
        
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
