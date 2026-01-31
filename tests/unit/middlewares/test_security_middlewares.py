import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request, FastAPI, Response
from starlette.responses import JSONResponse
from web_admin.middlewares.context_middleware import ContextMiddleware
from web_admin.middlewares.rate_limit_middleware import RateLimitMiddleware
from core.context import user_id_var, username_var, ip_address_var, request_id_var
import time

# --- Context Middleware Tests ---

@pytest.mark.asyncio
async def test_context_middleware_sets_vars():
    # Setup
    app = FastAPI()
    middleware = ContextMiddleware(app)
    
    # Mock Call Next
    async def call_next(request):
        # Check vars inside the request context
        return {
            "user_id": user_id_var.get(),
            "ip": ip_address_var.get(),
            "req_id": request_id_var.get()
        }
        
    # Mock Request
    scope = {
        "type": "http",
        "client": ("192.168.1.100", 12345),
        "headers": [(b"user-agent", b"TestAgent")],
        "scheme": "http",
        "path": "/",
        "method": "GET"
    }
    request = Request(scope)
    
    # Execute
    result = await middleware.dispatch(request, call_next)
    
    # Verify
    assert result["ip"] == "192.168.1.100"
    assert result["req_id"] != "unknown"
    assert result["user_id"] is None # No token provided

@pytest.mark.asyncio
async def test_context_middleware_with_token():
    # Setup
    app = FastAPI()
    middleware = ContextMiddleware(app)
    
    # Mock JWT decode
    with patch("jwt.decode") as mock_jwt:
        mock_jwt.return_value = {"sub": "123", "name": "testuser"}
        
        async def call_next(request):
            return {
                "user_id": user_id_var.get(),
                "username": username_var.get()
            }
            
        # Mock Request with Cookie
        scope = {
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"cookie", b"access_token=valid_token")],
            "scheme": "http",
            "path": "/",
            "method": "GET"
        }
        request = Request(scope)
        
        # Execute
        result = await middleware.dispatch(request, call_next)
        
        # Verify
        assert result["user_id"] == 123
        assert result["username"] == "testuser"

# --- Rate Limit Middleware Tests ---

@pytest.mark.asyncio
async def test_rate_limit_middleware_allow():
    app = FastAPI()
    # Limit: 2 requests per 60 seconds
    middleware = RateLimitMiddleware(app, max_requests=2, window_seconds=60)
    
    async def call_next(request):
        return Response("OK")
        
    scope = {
        "type": "http",
        "client": ("10.0.0.1", 12345),
        "headers": [],
        "scheme": "http",
        "path": "/api/test",
        "method": "GET"
    }
    request = Request(scope)
    
    # 1. First Request -> OK
    resp = await middleware.dispatch(request, call_next)
    assert resp.status_code == 200
    
    # 2. Second Request -> OK
    resp = await middleware.dispatch(request, call_next)
    assert resp.status_code == 200
    
    # 3. Third Request -> 429
    resp = await middleware.dispatch(request, call_next)
    assert resp.status_code == 429

@pytest.mark.asyncio
async def test_rate_limit_bypass_localhost():
    app = FastAPI()
    middleware = RateLimitMiddleware(app, max_requests=1)
    
    async def call_next(request):
        return Response("OK")
        
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 12345),
        "headers": [],
        "scheme": "http",
        "path": "/api/test",
        "method": "GET"
    }
    request = Request(scope)
    
    # Should allow infinite
    for _ in range(5):
        resp = await middleware.dispatch(request, call_next)
        assert resp.status_code == 200
