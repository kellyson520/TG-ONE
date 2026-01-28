import pytest
import pyotp
from unittest.mock import patch, AsyncMock
from models.models import User
from core.container import container

@pytest.mark.asyncio
async def test_full_2fa_flow(client, db):
    # 0. Get initial CSRF token
    response = await client.get("/login")
    csrf_token = response.cookies.get("csrf_token")
    
    # 1. Create a test user
    from werkzeug.security import generate_password_hash
    username = "2fa_integration_user"
    password = "password123"
    
    user = User(
        username=username,
        password=generate_password_hash(password),
        is_active=True,
        is_admin=True
    )
    db.add(user)
    await db.commit()
    user_id = user.id # Get ID before any potential detached state issues

    def print_resp(label, r):
        print(f"\n[DEBUG] {label} Status: {r.status_code}")
        try:
            print(f"[DEBUG] {label} Body: {r.json()}")
        except:
            print(f"[DEBUG] {label} Text: {r.text[:200]}")

    # 2. Login (Initial - No 2FA)
    response = await client.post("/api/auth/login", json={
        "username": username,
        "password": password
    }, headers={"X-CSRF-Token": csrf_token})
    print_resp("Step 2 (Login)", response)
    assert response.status_code == 200
    login_data = response.json()
    token = login_data["access_token"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf_token
    }

    # 3. Setup 2FA
    response = await client.post("/api/auth/2fa/setup", headers=headers)
    print_resp("Step 3 (Setup)", response)
    assert response.status_code == 200
    setup_data = response.json()
    secret = setup_data["secret"]

    # 4. Enable 2FA
    totp = pyotp.TOTP(secret)
    token_2fa = totp.now()
    
    response = await client.post("/api/auth/2fa/enable", json={"token": token_2fa}, headers=headers)
    print_resp("Step 4 (Enable)", response)
    assert response.status_code == 200

    # 5. Login again (Should require 2FA)
    response = await client.post("/api/auth/login", json={
        "username": username,
        "password": password
    }, headers={"X-CSRF-Token": csrf_token})
    print_resp("Step 5 (2nd Login)", response)
    assert response.status_code == 202
    resp_22 = response.json()
    pre_auth_token = resp_22["pre_auth_token"]

    # 5.5 Clear last_otp_token using fresh session to avoid transaction issues
    async with container.db.session() as session:
        db_user = await session.get(User, user_id)
        if db_user:
            db_user.last_otp_token = None
            await session.commit()

    # 6. Complete 2FA Login
    token_2fa_new = totp.now()
    response = await client.post("/api/auth/login/2fa", json={
        "pre_auth_token": pre_auth_token,
        "token": token_2fa_new
    }, headers={"X-CSRF-Token": csrf_token})
    print_resp("Step 6 (Verify 2FA)", response)
    
    assert response.status_code == 200
    final_data = response.json()
    assert "access_token" in final_data
    
    # Verify the new token works
    new_token = final_data["access_token"]
    headers_final = {
        "Authorization": f"Bearer {new_token}",
        "X-CSRF-Token": csrf_token
    }
    response = await client.get("/api/system/stats", headers=headers_final)
    print_resp("Step 7 (Final Verification)", response)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_ip_guard_integration_mocked(client):
    """
    Test that IPGuardMiddleware correctly blocks requests when service denies access.
    """
    # 1. Test Blocked
    with patch("services.access_control_service.AccessControlService.check_ip_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = False
        response = await client.get("/api/system/stats")
        # Middleware is FIRST, so it should block BEFORE reaching auth dependencies (401)
        assert response.status_code == 403
        assert "Access Forbidden" in response.json()["detail"]

    # 2. Test Allowed (but still 401 because no login, but NOT 403)
    with patch("services.access_control_service.AccessControlService.check_ip_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True
        response = await client.get("/api/system/stats")
        assert response.status_code == 401
