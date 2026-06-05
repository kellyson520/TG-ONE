import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient
import secrets
from werkzeug.security import generate_password_hash as get_password_hash
from core.container import container
from models.models import User

@pytest.fixture
async def auth_headers(client: AsyncClient):
    """
    创建一个用户并登录
    stats 接口通常只需要 login_required (普通用户即可)
    """
    username = f"user_stats_{secrets.token_hex(4)}"
    password = "password123"
    
    user = User(
        username=username,
        email=f"{username}@test.com",
        password=get_password_hash(password),
        is_active=True,
        is_admin=False
    )
    
    async with container.db.session() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)

    # 登录
    page_resp = await client.get("/login")
    csrf_token = page_resp.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_token, "Accept": "application/json"}
    
    login_resp = await client.post("/api/auth/login", json={
        "username": username,
        "password": password
    }, cookies=page_resp.cookies, headers=headers)
    
    assert login_resp.status_code == 200
    return login_resp.cookies

@pytest.mark.asyncio
async def test_get_system_resources(client: AsyncClient, auth_headers):
    # Mock psutil
    mock_psutil = MagicMock()
    mock_psutil.cpu_percent.return_value = 15.5
    mock_psutil.virtual_memory.return_value.percent = 45.0
    mock_psutil.virtual_memory.return_value.used = 1024 * 1024 * 500 # 500MB
    mock_psutil.virtual_memory.return_value.total = 1024 * 1024 * 1000 # 1000MB
    mock_psutil.disk_usage.return_value.percent = 60.0
    mock_psutil.disk_usage.return_value.used = 1024 * 1024 * 1024 * 50 # 50GB
    mock_psutil.disk_usage.return_value.total = 1024 * 1024 * 1024 * 100 # 100GB
    
    with patch("web_admin.routers.stats_router.psutil", mock_psutil):
        resp = await client.get("/api/stats/system_resources", cookies=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        
        stats = data['data']
        assert stats['cpu_percent'] == 15.5
        assert stats['memory_percent'] == 45.0
        assert stats['disk_percent'] == 60.0
        assert 'db_size_mb' in stats
        assert 'queue_size' in stats

@pytest.mark.asyncio
async def test_get_stats_series(client: AsyncClient, auth_headers):
    # 7 days
    resp = await client.get("/api/stats/series?days=7", cookies=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert 'labels' in data['data']
    assert 'series' in data['data']

    # 24h
    resp = await client.get("/api/stats/series?period=24h", cookies=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert isinstance(data['data']['series'], list)

@pytest.mark.asyncio
async def test_get_stats_fragment(client: AsyncClient, auth_headers):
    # 此接口返回 HTML
    resp = await client.get("/api/system/stats_fragment", cookies=auth_headers)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    
    content = resp.text
    # 检查是否包含一些关键的统计卡片标题
    assert "总规则数" in content
    assert "活跃规则" in content
    assert "今日转发" in content
    assert "去重缓存" in content
