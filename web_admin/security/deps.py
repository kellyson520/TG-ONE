from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyCookie
from services.authentication_service import authentication_service
from models.models import User
from web_admin.security.exceptions import PageRedirect
from typing import Optional
import logging

logger = logging.getLogger(__name__)

cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)

async def get_current_user(
    request: Request,
    response: Response,
    access_token: Optional[str] = Depends(cookie_scheme)
) -> Optional[User]:
    """
    Get current user from access_token cookie.
    If access token is invalid/expired, attempts to refresh using refresh_token cookie.
    """
    # 1. Try Token (Authorization Header FIRST for consistency)
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not token:
        token = access_token
        if not token:
            logger.warning(f"Authentication failed: No token found in header or cookie. Headers: {request.headers.keys()}")
            
    if token:
        user = await authentication_service.get_user_from_token(token)
        if user:
            return user
        else:
            logger.warning(f"Authentication failed: Invalid access token (decode failed or user not found).")
            # Try refresh if access token is invalid but present?
            # get_user_from_token returns None if invalid. 
            # We strictly should try refresh token below.

    # 2. Try Refresh Token
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # logger.debug("Access token missing/invalid, attempting refresh")
        tokens = await authentication_service.refresh_access_token(refresh_token)
        
        if tokens:
            new_access_token, new_refresh_token = tokens
            # Set new cookies
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
            logger.info("Access & Refresh tokens rotated automatically via middleware")
            
            # Get user from new token
            user = await authentication_service.get_user_from_token(new_access_token)
            return user
        else:
             logger.warning("Authentication failed: Refresh token invalid or revoked.")
    else:
        logger.warning(f"Authentication failed: No refresh token cookie found. Cookies: {request.cookies.keys()}")

    return None

async def login_required(request: Request, user: Optional[User] = Depends(get_current_user)):
    """
    Ensure user is logged in. 
    Redirects to /login for HTML requests, 401 for API.
    """
    if not user:
        # Check if API request
        if request.url.path.startswith('/api/'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        else:
            # Web page request - Raise Redirect exception to stop execution
            raise PageRedirect(url="/login")
    return user

async def admin_required(request: Request, user: User = Depends(login_required)):
    """
    Ensure user is admin.
    """
    # No need to check RedirectResponse instance anymore as we raise Exception
        
    if not getattr(user, "is_admin", False):
        if request.url.path.startswith('/api/'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privilege required"
            )
        else:
            # For web pages, maybe show 403 page or redirect home
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    return user
