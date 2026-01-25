import pytest
from httpx import AsyncClient
import secrets
from werkzeug.security import generate_password_hash as get_password_hash

@pytest.fixture
async def admin_access_token(client: AsyncClient):
    """获取管理员用户的 Access Token 和 CSRF Token"""
    # 1. 登录管理员
    login_data = {
        "username": "admin",
        "password": "password"
    }
    # 假设 conftest.py 中已经有预置的 admin 用户
    # 如果没有，可能需要先创建一个。
    # 根据 conftest.py/setup_database，数据库是清空的，所以需要先创建用户。
    # 这里我们直接在测试中创建用户。
    pass

@pytest.fixture
async def regular_user_token(client: AsyncClient):
    """获取普通用户的 Access Token"""
    pass

@pytest.mark.asyncio
async def test_list_users_unauthorized(client: AsyncClient):
    resp = await client.get("/api/users")
    assert resp.status_code in [401, 403]

@pytest.mark.asyncio
async def test_user_management_flow(client: AsyncClient):
    # 1. 创建管理员和普通用户
    from core.container import container
    from models.models import User
    
    admin_user = User(
        username="admin_test",
        email="admin@test.com",
        password=get_password_hash("password"),  # Corrected field name
        is_active=True,
        is_admin=True
    )
    regular_user = User(
        username="user_test",
        email="user@test.com",
        password=get_password_hash("password"),  # Corrected field name
        is_active=True,
        is_admin=False
    )
    
    async with container.db.session() as session:
        session.add(admin_user)
        session.add(regular_user)
        await session.commit()
        await session.refresh(admin_user)
        await session.refresh(regular_user)
        admin_id = admin_user.id
        user_id = regular_user.id

    # 2. 只有管理员登录
    # 先获取 CSRF Token
    page_resp = await client.get("/login")
    csrf_token = page_resp.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_token, "Accept": "application/json"}
    
    login_resp = await client.post("/login", data={
        "username": "admin_test",
        "password": "password"
    }, cookies=page_resp.cookies, headers=headers)
    assert login_resp.status_code == 200
    cookies = login_resp.cookies
    
    # 3. 获取 CSRF Token (模拟前端行为，或者直接从 Cookie 中读取如果有)
    # 集成测试中，我们通常手动生成一个 CSRF token 并放入 header/cookie
    csrf_token = secrets.token_hex(32)
    cookies["csrf_token"] = csrf_token
    headers = {"X-CSRF-Token": csrf_token}

    # 4. 获取用户列表
    resp = await client.get("/api/users", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert len(data['data']) >= 2
    
    # 5. 切换普通用户为管理员
    resp = await client.post(
        f"/api/users/{user_id}/toggle_admin", 
        cookies=cookies,
        headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()['data']['is_admin'] is True
    
    # 6. 切换普通用户激活状态
    resp = await client.post(
        f"/api/users/{user_id}/toggle_active",
        cookies=cookies,
        headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()['data']['is_active'] is False
    
    # 7. 删除用户
    resp = await client.delete(
        f"/api/users/{user_id}",
        cookies=cookies,
        headers=headers
    )
    assert resp.status_code == 200
    
    # 验证删除
    async with container.db.session() as session:
        u = await session.get(User, user_id)
        assert u is None

@pytest.mark.asyncio
async def test_regular_user_forbidden(client: AsyncClient):
    # 1. 创建普通用户
    from core.container import container
    from models.models import User
    
    regular_user = User(
        username="user_forbidden",
        email="user_f@test.com",
        password=get_password_hash("password"),
        is_active=True,
        is_admin=False
    )
    
    async with container.db.session() as session:
        session.add(regular_user)
        await session.commit()
    
    # 2. 登录
    page_resp = await client.get("/login")
    csrf_token = page_resp.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_token, "Accept": "application/json"}

    login_resp = await client.post("/login", data={
        "username": "user_forbidden",
        "password": "password"
    }, cookies=page_resp.cookies, headers=headers)
    cookies = login_resp.cookies
    
    # 3. 尝试访问管理接口
    resp = await client.get("/api/users", cookies=cookies)
    # Expect 403 Forbidden because api_list_users requires admin_required
    # Note: fastapi_app.py: admin_required checks for is_admin
    assert resp.status_code in [401, 403]
