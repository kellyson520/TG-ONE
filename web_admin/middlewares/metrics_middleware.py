from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
from core.observability.metrics import metrics_manager

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture Prometheus metrics for HTTP requests.
    """
    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself to avoid noise
        if request.url.path == "/metrics":
             return await call_next(request)

        start_time = time.time()
        method = request.method
        path = request.url.path
        
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # Exception will be handled by ExceptionMiddleware, but we record 500 here
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            # Record metrics
            metrics_manager.track_request(method, path, status_code)
            metrics_manager.observe_request_duration(method, path, duration)
