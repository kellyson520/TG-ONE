import pytest
from httpx import AsyncClient
from models.models import User

@pytest.fixture
async def auth_headers(client: AsyncClient, db):
    # 为测试准备管理员权限的 headers
    from web_admin.security.deps import admin_required, login_required
    from tests.conftest import get_app
    
    mock_user = User(id=1, username="admin", is_admin=True)
    app = get_app()
    app.dependency_overrides[admin_required] = lambda: mock_user
    app.dependency_overrides[login_required] = lambda: mock_user
    
    csrf_token = "test_csrf_user"
    headers = {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}"
    }
    yield headers
    app.dependency_overrides = {}

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
async def test_user_router_me(client, auth_headers):
    # 获取当前用户信息
    resp = await client.get("/api/users/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "admin"

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
async def test_user_list_and_toggle(client, auth_headers, db):
    # 1. 创建另外一个用户
    from repositories.user_repo import UserRepository
    from core.container import container
    repo = UserRepository(container.db)
    u2 = await repo.create_user("user_to_toggle", "password", is_admin=False)
    
    # 2. 列出用户
    resp = await client.get("/api/users", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()["data"]
    assert any(u["username"] == "user_to_toggle" for u in users)
    
    # 3. 切换管理员权限
    resp = await client.post(f"/api/users/{u2.id}/toggle_admin", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_admin"] is True
    
    # 验证数据库
    db.expire_all()
    updated_u2 = await repo.get_user_by_id(u2.id)
    assert updated_u2.is_admin is True

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
async def test_delete_user_protected(client, auth_headers, db):
    # 设置内置管理员 ID 为 1
    # 尝试删除 ID 为 1 的用户 (应被拦截)
    resp = await client.delete("/api/users/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "内置管理员不能删除" in resp.json()["error"]
