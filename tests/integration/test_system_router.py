import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

@pytest.fixture
async def auth_headers(client: AsyncClient):
    # 为测试准备管理员权限的 headers
    # 覆盖 admin_required 依赖
    from web_admin.security.deps import admin_required, login_required
    from models.models import User
    from tests.conftest import get_app
    
    mock_user = User(id=1, username="admin", is_admin=True)
    app = get_app()
    app.dependency_overrides[admin_required] = lambda: mock_user
    app.dependency_overrides[login_required] = lambda: mock_user
    
    csrf_token = "test_csrf"
    headers = {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}"
    }
    yield headers
    # 清理覆盖
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_tasks_list(client, auth_headers):
    resp = await client.get("/api/system/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "items" in data["data"]

@pytest.mark.asyncio
async def test_get_system_stats(client, auth_headers):
    # Mock guard_service.get_stats
    with patch("services.system_service.guard_service.get_stats") as mock_stats:
        mock_stats.return_value = {"cpu": 10, "memory": 20}
        
        resp = await client.get("/api/system/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "rules" in data["data"]
        assert "system" in data["data"]
        assert data["data"]["system"]["cpu"] == 10

@pytest.mark.asyncio
async def test_get_config(client, auth_headers):
    resp = await client.get("/api/system/config", headers=auth_headers)
    assert resp.status_code == 200
    assert "bot_token_set" in resp.json()["data"]

@pytest.mark.asyncio
async def test_update_config_error(client, auth_headers):
    # 测试无效输入
    resp = await client.post("/api/system/config", json={"history_message_limit": "invalid"}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["success"] is False

@pytest.mark.asyncio
async def test_get_db_pool_status(client, auth_headers):
    resp = await client.get("/api/system/db-pool", headers=auth_headers)
    assert resp.status_code == 200
    assert "pool" in resp.json()["data"]

@pytest.mark.asyncio
async def test_get_websocket_stats(client, auth_headers):
    resp = await client.get("/api/system/websocket/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert "data" in resp.json()
