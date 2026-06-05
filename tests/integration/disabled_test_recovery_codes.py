
import pytest
from httpx import AsyncClient
from werkzeug.security import generate_password_hash
from models.models import User
import logging

logger = logging.getLogger(__name__)

@pytest.fixture
async def test_user(db):
    """Create a test user"""
    import uuid
    user = User(
        username=f"recovery_test_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password123"),
        is_active=True,
        is_admin=True,
        is_2fa_enabled=True  # simulate 2FA enabled
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@pytest.fixture
async def auth_client(client: AsyncClient, test_user):
    """Return an authenticated client"""
    from services.authentication_service import authentication_service
    # Create session directly to skip login API call
    access_token, _ = await authentication_service.create_session(
        test_user.id, "127.0.0.1", "test-agent"
    )
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    return client

@pytest.mark.asyncio
async def test_generate_recovery_codes(auth_client):
    """Test generating recovery codes"""
    response = await auth_client.post("/api/auth/2fa/recovery-codes")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["codes"]) == 10
    assert data["total"] == 10
    
    # Check format XXXX-XXXX
    code = data["codes"][0]
    assert len(code) == 9
    assert "-" in code

@pytest.mark.asyncio
async def test_get_recovery_status(auth_client):
    """Test getting recovery codes status"""
    # First generate codes
    await auth_client.post("/api/auth/2fa/recovery-codes")
    
    response = await auth_client.get("/api/auth/2fa/recovery-codes/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 10
    assert data["used"] == 0
    assert data["remaining"] == 10
    assert data["has_codes"] is True

@pytest.mark.asyncio
async def test_verify_and_consume_code(auth_client, test_user):
    """Test verify and consume a recovery code"""
    # Generate codes
    res = await auth_client.post("/api/auth/2fa/recovery-codes")
    codes = res.json()["codes"]
    first_code = codes[0]
    
    # Verify valid code
    verify_res = await auth_client.post("/api/auth/2fa/recovery-codes/verify", json={"code": first_code})
    assert verify_res.status_code == 200
    assert verify_res.json()["success"] is True
    
    # Check status update
    status_res = await auth_client.get("/api/auth/2fa/recovery-codes/status")
    status_data = status_res.json()
    assert status_data["used"] == 1
    assert status_data["remaining"] == 9
    
    # Verify reuse fails
    verify_res_2 = await auth_client.post("/api/auth/2fa/recovery-codes/verify", json={"code": first_code})
    assert verify_res_2.status_code == 401 # Unauthorized or Bad Request depending on implementation

@pytest.mark.asyncio
async def test_login_with_recovery_code(client, test_user):
    """Test login flow using recovery code"""
    from services.authentication_service import authentication_service
    # 1. Setup codes for user (need auth first)
    access_token, _ = await authentication_service.create_session(
        test_user.id, "127.0.0.1", "test-agent"
    )
    setup_headers = {"Authorization": f"Bearer {access_token}"}
    res = await client.post("/api/auth/2fa/recovery-codes", headers=setup_headers)
    code = res.json()["codes"][0]
    
    # 2. Start Login (get pre-auth token)
    # Mocking pre-auth token creation manually to skip password check
    pre_auth_token = authentication_service.create_pre_auth_token(test_user.id)
    
    # 3. Use recovery code to login
    login_res = await client.post("/api/auth/login/recovery", json={
        "pre_auth_token": pre_auth_token,
        "token": code
    })
    
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    # 4. Verify code consumed
    status_res = await client.get("/api/auth/2fa/recovery-codes/status", headers=setup_headers)
    assert status_res.json()["used"] == 1
