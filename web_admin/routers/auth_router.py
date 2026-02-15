from fastapi import APIRouter, Depends, HTTPException, status, Request, Response

from core.config import settings
import jwt
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.authentication_service import authentication_service
from core.container import container
from services.active_session_service import active_session_service
from services.audit_service import audit_service
import logging

logger = logging.getLogger(__name__)

# Using dependencies from web_admin.security.deps
from web_admin.security.deps import get_current_user, login_required, admin_required

# New imports for enhanced security
from fastapi import Form, Query
from web_admin.security.rate_limiter import get_rate_limiter
from web_admin.security.password_validator import PasswordValidator, get_password_strength
from services.system_service import system_service
import re

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class Verify2FALoginRequest(BaseModel):
    pre_auth_token: str
    token: str

class Verify2FASetupRequest(BaseModel):
    token: str

class Setup2FAResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_code: str

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login", response_model=None) # Response model varies (TokenResponse or JSONResponse for errors/2FA)
async def login(
    request: Request,
    response: Response
):
    """
    Login with username and password. Supports both Form data (Swagger UI) and JSON.
    Includes Rate Limiting and Account Locking.
    """
    username = ""
    password = ""
    
    # 1. Try JSON
    try:
        if "application/json" in request.headers.get("content-type", ""):
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
    except Exception as e:
        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        
    # 2. Try Form (if not found in JSON)
    if not username:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception as e:
            # logger.warning(f"Login form parsing failed: {e}")
            pass

    if not username or not password:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )

    # --- Rate Limiting & Lockout Check ---
    rate_limiter = get_rate_limiter()
    client_ip = request.client.host if request.client else "unknown"
    
    if rate_limiter.is_locked(username):
        lockout_info = rate_limiter.get_lockout_info(username)
        remaining_minutes = lockout_info['remaining_minutes']
        remaining_seconds = lockout_info['remaining_seconds'] % 60
        
        logger.warning(f"Login refused (Account Locked): username={username}, ip={client_ip}")
        
        await audit_service.log_event(
            action="LOGIN_LOCKED",
            username=username,
            ip_address=client_ip,
            status="failure",
            details={"reason": "account_locked"}
        )
        
        return JSONResponse({
            'success': False,
            'error': f'账户已锁定，请在 {remaining_minutes} 分 {remaining_seconds} 秒后重试',
            'locked': True,
            'unlock_at': lockout_info['unlock_at'],
            'remaining_seconds': lockout_info['remaining_seconds']
        }, status_code=429)

    # --- Authenticate ---
    # We use authentication_service for user fetching, but we need to handle the password check manually 
    # to integrate with rate_limiter failure recording (or pass rate-limiter logic into service, 
    # but here we are doing it in the controller as per legacy fastapi_app logic).
    
    # Actually authentication_service.authenticate_user does checks.
    # Let's verify if we should use valid user object or handle failure explicitly.
    
    user = await authentication_service.authenticate_user(username, password)
    
    # Fallback: Environment Admin Check (if DB empty or specific env set)
    if not user:
        # Check env (copied from fastapi_app.py)
        # Check env (copied from fastapi_app.py)
        env_u = settings.WEB_ADMIN_USERNAME or ''
        env_p = settings.WEB_ADMIN_PASSWORD or ''
        if username == env_u and password == env_p and env_u and env_p:
            # Create/Get user logic could be complex here, assuming authenticate_user handles db users.
            # If env user matches, we might just proceed or create it on the fly.
            # For strictness, let's rely on container.user_repo inside authentication_service?
            # authentication_service.authenticate_user uses user_repo.
            # If env user is used, we should probably ensure it exists in DB.
            # Logic from fastapi_app:
            u_repo = await container.user_repo.get_user_by_username(username)
            if not u_repo:
                 user = await container.user_repo.create_user(env_u, env_p, is_admin=True)
                 logger.info(f"Created admin from ENV: {env_u}")
            else:
                 # If user exists but password mismatch in authenticate_user (which checks hash),
                 # checking env_p again is weird unless we want to reset it?
                 # Let's stick to the behavior: if authenticate_user failed, WE FAIL.
                 # The env check in fastapi_app was likely for *bootstrapping*.
                 pass

    if not user:
        # Record Failure
        is_locked = rate_limiter.record_failure(username, client_ip)
        
        if is_locked:
            logger.error(f"Account Locked (Too many failures): username={username}, ip={client_ip}")
            lockout_info = rate_limiter.get_lockout_info(username)
            
            await audit_service.log_event(
                action="LOGIN_LOCKOUT",
                username=username,
                ip_address=client_ip,
                status="failure",
                details={"reason": "max_attempts_exceeded"}
            )

            return JSONResponse({
                'success': False,
                'error': f'登录失败次数过多，账户已锁定 {lockout_info["remaining_minutes"]} 分钟',
                'locked': True,
                'unlock_at': lockout_info['unlock_at']
            }, status_code=429)
        
        await audit_service.log_event(
            action="LOGIN_FAILED",
            username=username,
            ip_address=client_ip,
            status="failure",
            details={"reason": "invalid_credentials"}
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # --- Success ---
    rate_limiter.record_success(username)
    
    # Check 2FA
    if getattr(user, 'is_2fa_enabled', False):
        pre_auth_token = authentication_service.create_pre_auth_token(user.id)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "2fa_required",
                "message": "Two-factor authentication required",
                "pre_auth_token": pre_auth_token
            }
        )

    # Get IP and UA
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")

    # Create session
    access_token, refresh_token = await authentication_service.create_session(user.id, ip, ua)
    
    # Set cookies for web access
    secure = settings.COOKIE_SECURE
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=secure, 
        path="/",
        max_age=max_age
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        samesite="lax", 
        secure=secure,
        path="/",
        max_age=refresh_max_age
    )

    # Audit Log
    await audit_service.log_event(
        action="LOGIN",
        user_id=user.id,
        username=user.username,
        ip_address=ip,
        user_agent=ua,
        status="success"
    )

    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer",
        "success": True,
        "message": "Login successful"
    }

@router.get("/me")
async def get_current_user_profile(user = Depends(login_required)):
    """
    Get current logged in user details.
    """
    return {
        "id": user.id,
        "username": user.username,
        "role": "admin" if user.is_admin else "user",
        "email": getattr(user, "email", ""),
        "created_at": user.created_at.isoformat() if hasattr(user.created_at, "isoformat") else user.created_at,
        "is_2fa_enabled": getattr(user, "is_2fa_enabled", False),
        "last_login": user.last_login.isoformat() if hasattr(user.last_login, "isoformat") else user.last_login
    }

@router.post("/login/2fa", response_model=TokenResponse)
async def login_2fa(
    request: Request,
    response: Response,
    verify_data: Verify2FALoginRequest
):
    """
    Complete login with 2FA token.
    """
    # Verify pre_auth_token
    try:
        payload = jwt.decode(verify_data.pre_auth_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "pre_auth":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired pre-auth token")
        
    # Verify OTP
    if not await authentication_service.verify_2fa_login(user_id, verify_data.token):
        await audit_service.log_event(
            action="LOGIN_2FA_FAIL",
            user_id=user_id,
            status="failure",
            details="Invalid OTP"
        )
        raise HTTPException(status_code=401, detail="Invalid authentication code")
        
    # Success - Create Session
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    
    access_token, refresh_token = await authentication_service.create_session(user_id, ip, ua)
    
    # Audit Log
    user = await container.user_repo.get_user_by_id(user_id)
    await audit_service.log_event(
        action="LOGIN",
        user_id=user_id,
        username=user.username if user else "unknown",
        ip_address=ip,
        user_agent=ua,
        status="success",
        details="via 2FA"
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        samesite="lax", 
        secure=False,
        path="/"
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer",
        "success": True
    }


# --- Register Endpoint ---
@router.post("/register", response_class=JSONResponse)
async def register(
    username: str = Form(...),
    password: str = Form(...)
):
    """
    User Registration
    """
    if not system_service.get_allow_registration():
        return JSONResponse({'success': False, 'error': '注册已关闭'}, status_code=403)
    
    if not username or not password:
        return JSONResponse({'success': False, 'error': '参数缺失'}, status_code=400)
    
    try:
        # 1. Username Validation
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            return JSONResponse({
                'success': False,
                'error': '用户名格式不正确（3-20个字符，仅限字母数字下划线）'
            }, status_code=400)
        
        # 2. Password Strength
        is_valid, error_message = PasswordValidator.validate(password)
        if not is_valid:
            return JSONResponse({
                'success': False,
                'error': error_message,
                'password_requirements': PasswordValidator.get_missing_requirements(password)
            }, status_code=400)
        
        # 3. Check Existence
        existing_user = await container.user_repo.get_user_by_username(username)
        if existing_user:
            return JSONResponse({'success': False, 'error': '用户名已存在'}, status_code=409)
        
        # 4. Create User
        await container.user_repo.create_user(username, password, is_admin=False)
        
        logger.info(f"New user registered: username={username}")
        
        await audit_service.log_event(
            action="REGISTER",
            username=username,
            status="success"
        )

        return JSONResponse({'success': True, 'message': '注册成功，请登录'})
        
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        await audit_service.log_event(
            action="REGISTER_FAILED",
            username=username,
            status="failure",
            details={"error": str(e)}
        )
        return JSONResponse({'success': False, 'error': '注册失败，请稍后重试'}, status_code=500)

@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    """
    Refresh access token using refresh token from cookie or header.
    """
    # Try getting from cookie first
    refresh_token = request.cookies.get("refresh_token")
    
    # If not in cookie, try authorization header or body? 
    # Usually refresh is explicit.
    if not refresh_token:
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    tokens = await authentication_service.refresh_access_token(refresh_token)
    
    if not tokens:
        # Token invalid or revoked
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Tokens are now a tuple: (new_access_token, new_refresh_token)
    new_access_token, new_refresh_token = tokens
        
    # Audit Log
    await audit_service.log_event(
        action="REFRESH_TOKEN",
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
        status="success",
        details={"rotated": True}
    )
        
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    
    return {
        "access_token": new_access_token, 
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Logout user, revoke session.
    """
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await authentication_service.revoke_session(refresh_token)
    
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    
    # Audit Log
    await audit_service.log_event(
        action="LOGOUT",
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
        status="success"
    )
    
    return {"message": "Logged out successfully"}

@router.get("/sessions")
async def get_active_sessions(
    request: Request, 
    user = Depends(login_required)
):  
    """
    Get all active sessions. 
    If user is admin, returns all sessions.
    If normal user, returns only their own sessions.
    """
    target_user_id = None
    if not user.is_admin:
        target_user_id = user.id
        
    sessions = await active_session_service.get_all_sessions(user_id=target_user_id)
    return {"success": True, "count": len(sessions), "data": sessions}


# ==================== Security APIs ====================

@router.get("/lockout_status", response_class=JSONResponse)
async def get_lockout_status(username: str = Query(...)):
    """
    Check account lockout status
    """
    try:
        rate_limiter = get_rate_limiter()
        lockout_info = rate_limiter.get_lockout_info(username)
        
        if lockout_info:
            return JSONResponse({'success': True, 'data': lockout_info})
        else:
            return JSONResponse({'success': True, 'data': None})
    except Exception as e:
        logger.error(f"Failed to check lockout status: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/unlock_account", response_class=JSONResponse)
async def unlock_account(
    request: Request,
    username: str = Form(...),
    user = Depends(admin_required)
):
    """
    Manually unlock account (Admin only)
    """
    try:
        rate_limiter = get_rate_limiter()
        rate_limiter.unlock(username)
        
        logger.info(f"Admin {user.username} unlocked account: {username}")
        
        return JSONResponse({'success': True, 'message': f'账户 {username} 已解锁'})
    except Exception as e:
        logger.error(f"Failed to unlock account: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.post("/check_password_strength", response_class=JSONResponse)
async def check_password_strength(password: str = Form(...)):
    """
    Check password strength
    """
    try:
        strength_info = get_password_strength(password)
        return JSONResponse({'success': True, 'data': strength_info})
    except Exception as e:
        logger.error(f"Failed to check password strength: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.get("/rate_limiter_stats", response_class=JSONResponse)
async def get_rate_limiter_stats(user = Depends(admin_required)):
    """
    Get rate limiter statistics (Admin only)
    """
    try:
        rate_limiter = get_rate_limiter()
        stats = rate_limiter.get_stats()
        return JSONResponse({'success': True, 'data': stats})
    except Exception as e:
        logger.error(f"Failed to get rate limiter stats: {str(e)}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@router.delete("/sessions/{session_id}")
async def revoke_session_by_id(
    session_id: int, 
    user = Depends(admin_required)
):
    """
    Revoke a specific session (Admin only).
    """
    await active_session_service.revoke_session(session_id)
    
    # Audit Log
    await audit_service.log_event(
        action="REVOKE_SESSION",
        user_id=user.id,
        username=user.username,
        resource_type="SESSION",
        resource_id=str(session_id),
        status="success"
    )
    return {"success": True, "message": f"Session {session_id} revoked"}

@router.delete("/sessions/user/{user_id}")
async def revoke_user_sessions(
    user_id: int, 
    user = Depends(admin_required)
):
    """
    Revoke all sessions for a specific user (Admin only).
    """
    await active_session_service.revoke_user_sessions(user_id)
    
    # Audit Log
    await audit_service.log_event(
        action="REVOKE_USER_SESSIONS",
        user_id=user.id,
        username=user.username,
        resource_type="USER",
        resource_id=str(user_id),
        status="success"
    )
    return {"success": True, "message": f"All sessions for user {user_id} revoked"}
    return {"success": True, "message": f"All sessions for user {user_id} revoked"}

@router.post("/2fa/setup", response_model=Setup2FAResponse)
async def setup_2fa(user = Depends(login_required)):
    """Start 2FA setup: Generate secret and QR code."""
    try:
        secret, otpauth, qr_b64 = await authentication_service.generate_2fa_secret(user.id)
        return {
            "secret": secret,
            "otpauth_url": otpauth,
            "qr_code": qr_b64
        }
    except Exception as e:
        logger.error(f"2FA Setup Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate 2FA secret")

@router.post("/2fa/enable")
async def enable_2fa(
    verify_data: Verify2FASetupRequest,
    user = Depends(login_required)
):
    """Confirm 2FA setup by verifying code."""
    success = await authentication_service.verify_and_enable_2fa(user.id, verify_data.token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    await audit_service.log_event(
        action="ENABLE_2FA",
        user_id=user.id,
        username=user.username,
        status="success"
    )
    return {"success": True, "message": "2FA enabled successfully"}

@router.post("/2fa/disable")
async def disable_2fa(user = Depends(login_required)):
    """Disable 2FA."""
    # In production, might want to require password confirmation here
    success = await authentication_service.disable_2fa(user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to disable 2FA")
        
    await audit_service.log_event(
        action="DISABLE_2FA",
        user_id=user.id,
        username=user.username,
        status="success"
    )
    return {"success": True, "message": "2FA disabled successfully"}


# ===== Recovery Codes API =====

class RecoveryCodeVerifyRequest(BaseModel):
    code: str


@router.post("/2fa/recovery-codes")
async def generate_recovery_codes(request: Request, user = Depends(login_required)):
    """
    生成新的 2FA 备份码 (10 个)
    
    注意: 调用此接口会覆盖之前的所有备份码!
    备份码仅在此接口返回时展示一次，请妥善保存。
    """
    try:
        codes = await authentication_service.generate_recovery_codes(user.id)
        
        # 记录审计日志
        await audit_service.log_event(
            action="GENERATE_RECOVERY_CODES",
            user_id=user.id,
            username=user.username,
            ip_address=request.client.host if request.client else "unknown",
            status="success"
        )
        
        return {
            "success": True,
            "message": "Recovery codes generated. Save them securely!",
            "codes": codes,
            "total": len(codes)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Generate recovery codes error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate recovery codes")


@router.get("/2fa/recovery-codes/status")
async def get_recovery_codes_status(user = Depends(login_required)):
    """
    获取备份码状态 (总数/已使用/剩余)
    """
    status = await authentication_service.get_recovery_codes_status(user.id)
    return {
        "success": True,
        **status
    }


@router.post("/2fa/recovery-codes/verify")
async def verify_recovery_code(
    request: Request,
    data: RecoveryCodeVerifyRequest,
    user = Depends(login_required)
):
    """
    验证并消费一个备份码
    
    用于测试备份码是否有效 (会消耗该备份码!)
    """
    success = await authentication_service.verify_recovery_code(user.id, data.code)
    
    # 记录审计日志
    await audit_service.log_event(
        action="2FA_RECOVERY_USED" if success else "2FA_RECOVERY_FAILED",
        user_id=user.id,
        username=user.username,
        ip_address=request.client.host if request.client else "unknown",
        status="success" if success else "failure"
    )
    
    if not success:
        raise HTTPException(status_code=401, detail="Invalid or already used recovery code")
    
    return {
        "success": True,
        "message": "Recovery code verified and consumed"
    }


@router.post("/login/recovery")
async def login_with_recovery_code(
    request: Request,
    response: Response,
    verify_data: Verify2FALoginRequest  # 复用: pre_auth_token + token (备份码)
):
    """
    使用备份码完成 2FA 登录 (替代 OTP)
    
    当用户丢失 Authenticator 时使用
    """
    # Verify pre_auth_token
    try:
        payload = jwt.decode(verify_data.pre_auth_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "pre_auth":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired pre-auth token")
    
    # Verify Recovery Code
    if not await authentication_service.verify_recovery_code(user_id, verify_data.token):
        await audit_service.log_event(
            action="LOGIN_RECOVERY_FAIL",
            user_id=user_id,
            ip_address=request.client.host if request.client else "unknown",
            status="failure"
        )
        raise HTTPException(status_code=401, detail="Invalid or already used recovery code")
    
    # Success - Create Session
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    
    access_token, refresh_token = await authentication_service.create_session(user_id, ip, ua)
    
    # Audit Log
    user = await container.user_repo.get_user_by_id(user_id)
    await audit_service.log_event(
        action="LOGIN",
        user_id=user_id,
        username=user.username if user else "unknown",
        ip_address=ip,
        user_agent=ua,
        status="success",
        details={"via": "recovery_code"}
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        samesite="lax", 
        secure=False,
        path="/"
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer"
    }

