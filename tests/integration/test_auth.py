
import pytest
from httpx import AsyncClient
from datetime import timedelta
from services.authentication_service import authentication_service
from models.models import User
import asyncio

@pytest.mark.asyncio
async def test_auth_auto_refresh(client: AsyncClient, db, clear_data):
    """
    Test that deps.py automatically refreshes access token if expired but refresh token is valid.
    Integration test for Task 2.1: Authentication Hardening (Refresh Token).
    """
    # 1. Create User
    user = User(username="authtest", password="hashed_pw", is_active=True, is_admin=False)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 2. Login (Create Session)
    # create_session creates tokens and stores in DB
    access_token, refresh_token = await authentication_service.create_session(
        user.id, "127.0.0.1", "pytest"
    )

    # 3. Create Expired Access Token manually
    # We simulate an expired token by creating one with past expiration
    expired_access = authentication_service.create_access_token(
        {"sub": str(user.id)}, expires_delta=timedelta(minutes=-10)
    )

    # 4. Request with Expired Access + Valid Refresh
    cookies = {
        "access_token": expired_access,
        "refresh_token": refresh_token
    }
    
    # Use a protected endpoint. /api/auth/sessions requires login.
    response = await client.get("/api/auth/sessions", cookies=cookies)

    # 5. Assert 
    # Current deps behavior: 401 Unauthorized (because get_current_user returns None)
    # Expected after fix: 200 OK and new access_token cookie
    
    if response.status_code == 401:
        pytest.fail("Auto-refresh not implemented yet (Got 401)")
        
    assert response.status_code == 200
    assert "access_token" in response.cookies
    new_access = response.cookies["access_token"]
    assert new_access != expired_access
