from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from core.context import user_id_var, username_var, ip_address_var, user_agent_var, request_id_var, trace_id_var
import jwt
from core.config import settings
import uuid
import logging

logger = logging.getLogger(__name__)

class ContextMiddleware(BaseHTTPMiddleware):
    """
    Context Middleware
    Initializes ContextVars for Request ID, User Identity, and IP.
    Must run BEFORE AuthMiddleware/Endpoints to ensure context is available.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Request ID
        req_id = str(uuid.uuid4())
        token_req_id = request_id_var.set(req_id)
        
        # 2. Trace ID (Sync with Request ID if not present)
        current_trace = trace_id_var.get()
        token_trace = None
        if current_trace == "-":
             token_trace = trace_id_var.set(req_id)

        # 3. IP and UA
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "unknown")
        token_ip = ip_address_var.set(ip)
        token_ua = user_agent_var.set(ua)

        # 4. User Identity (Best Effort Extraction)
        token_user_id = None
        token_username = None
        
        # Try Cookie first then Header
        token = request.cookies.get("access_token")
        if not token:
             auth_header = request.headers.get("Authorization")
             if auth_header and auth_header.startswith("Bearer "):
                 token = auth_header.split(" ")[1]
        
        if token:
            try:
                # We trust the signature for Logging Context purposes.
                # Actual security enforcement happens in route dependencies.
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                user_id = payload.get("sub")
                if user_id:
                     token_user_id = user_id_var.set(int(user_id))
                     
                     # Try to get username if available, else format ID
                     # Note: Our current JWT creation might not include username. 
                     # If we want it, we should add it to payload in authentication_service.
                     username = payload.get("name") or payload.get("username")
                     if username:
                         token_username = username_var.set(username)
                     else:
                         token_username = username_var.set(f"User_{user_id}")
            except Exception:
                # Ignore invalid tokens here, let Auth handle it
                pass

        try:
            response = await call_next(request)
            return response
        finally:
            # ContextVars are task-local, so strictly speaking reset isn't required if thread isn't reused 
            # across requests dirty, but in async frameworks it is safe.
            # However, for correctness in some pool scenarios:
            request_id_var.reset(token_req_id)
            if token_trace: trace_id_var.reset(token_trace)
            ip_address_var.reset(token_ip)
            user_agent_var.reset(token_ua)
            if token_user_id: user_id_var.reset(token_user_id)
            if token_username: username_var.reset(token_username)
