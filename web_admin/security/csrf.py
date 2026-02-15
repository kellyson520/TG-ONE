import secrets
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. 获取或生成 CSRF Cookie
        csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
        should_set_cookie = False
        
        if not csrf_token:
            csrf_token = secrets.token_hex(32)
            should_set_cookie = True
            # 将新 Token 放入 Scope 供后续使用
            request.scope["csrf_token_new"] = csrf_token
            
        # 注入 State 供模板使用
        request.state.csrf_token = csrf_token
        
        # 2. 对非安全方法进行校验 (全局生效)
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            # 排除白名单路径
            if not request.url.path.startswith(("/static", "/healthz", "/readyz", "/api/auth/login")):
                try:
                    await validate_csrf(request)
                    logger.debug(f"CSRF token validation passed for {request.method} {request.url.path}")
                except HTTPException as e:
                    logger.warning(f"CSRF token validation failed for {request.method} {request.url.path}: {e.detail}")
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
                except Exception as ex:
                    logger.error(f"CSRF 校验崩溃: {str(ex)} for {request.method} {request.url.path}", exc_info=True)
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=403, content={"detail": "CSRF Verification Failed"})
        
        response = await call_next(request)
        
        # 3. 设置 Cookie
        if should_set_cookie or request.scope.get("csrf_token_new"):
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=request.scope.get("csrf_token_new") or csrf_token,
                httponly=False,
                samesite="lax",
                secure=False,
                path="/"
            )
            
        return response

from markupsafe import Markup

async def validate_csrf(request: Request):
    """
    CSRF 校验依赖
    检查 Header (API) 或 Form Data (页面提交)
    """
    if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME) or request.scope.get("csrf_token_new")
    if not cookie_token:
        # 如果中间件未生效或 Cookie 丢失
        raise HTTPException(status_code=403, detail="CSRF Cookie Missing")

    # 1. 检查 Header (优先)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if header_token and header_token == cookie_token:
        return

    # 2. 检查 Form Data
    # 注意：await request.form() 会缓存结果，不影响后续 Form(...) 获取
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            form_token = form.get("csrf_token")
            if form_token and form_token == cookie_token:
                return
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

    raise HTTPException(status_code=403, detail="CSRF Token Verification Failed")

def csrf_token_input(request: Request) -> Markup:
    """生成 HTML 隐藏域，用于模板中的表单提交"""
    token = getattr(request.state, "csrf_token", "")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')
