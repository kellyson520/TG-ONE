import pytest
from httpx import AsyncClient
import secrets
from werkzeug.security import generate_password_hash as get_password_hash
from core.container import container
from models.models import User

@pytest.fixture
async def logs_auth_headers(client: AsyncClient):
    username = f"admin_logs_{secrets.token_hex(4)}"
    password = "password123"
    
    admin_user = User(
        username=username,
        email=f"{username}@test.com",
        password=get_password_hash(password),
        is_active=True,
        is_admin=True
    )
    
    async with container.db.session() as session:
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

    page_resp = await client.get("/login")
    csrf_token = page_resp.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_token, "Accept": "application/json"}
    
    login_resp = await client.post("/api/auth/login", json={
        "username": username,
        "password": password
    }, cookies=page_resp.cookies, headers=headers)
    
    return login_resp.cookies

@pytest.fixture
def setup_log_files(tmp_path):
    """
    配置 Mock 的 env_config_manager 并创建临时日志文件
    """
    # 保证 settings.LOG_DIR 指向 tmp_path
    from core.config import settings
    original_log_dir = settings.LOG_DIR
    settings.LOG_DIR = str(tmp_path)
    
    # 也尝试 Mock env_config_manager 防止它被重新加载
    from core.helpers.env_config import env_config_manager
    
    def get_config_side_effect(key, default=None):
        if key == "LOG_DIR":
            return str(tmp_path)
        return getattr(settings, key, default)
        
    if hasattr(env_config_manager, "get_config"):
        env_config_manager.get_config.side_effect = get_config_side_effect
    
    # 创建测试日志文件
    log1 = tmp_path / "app.log"
    log1.write_text("2026-01-01 12:00:00 INFO Test log entry 1\nLine 2\nLine 3", encoding="utf-8")
    
    log2 = tmp_path / "error.log"
    log2.write_text("Error message here", encoding="utf-8")
    
    yield tmp_path
    
    # 恢复 settings
    settings.LOG_DIR = original_log_dir

@pytest.mark.asyncio
async def test_list_log_files(client: AsyncClient, logs_auth_headers, setup_log_files):
    resp = await client.get("/api/system/logs/list", cookies=logs_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    
    files = data['data']
    filenames = [f['name'] for f in files]
    assert "app.log" in filenames
    assert "error.log" in filenames

@pytest.mark.asyncio
async def test_tail_log(client: AsyncClient, logs_auth_headers, setup_log_files):
    # View app.log (was called tail)
    resp = await client.get("/api/system/logs/view?filename=app.log", cookies=logs_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    # data['data']['content'] is the content string
    content = data['data']['content']
    assert "Test log entry 1" in content

@pytest.mark.asyncio
async def test_download_log(client: AsyncClient, logs_auth_headers, setup_log_files):
    resp = await client.get("/api/system/logs/download?filename=error.log", cookies=logs_auth_headers)
    assert resp.status_code == 200
    # 应该是文件流
    assert "Error message here" in resp.text
