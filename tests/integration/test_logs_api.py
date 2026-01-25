import pytest
from httpx import AsyncClient
import secrets
from werkzeug.security import generate_password_hash as get_password_hash
from core.container import container
from models.models import User
import sys
from unittest.mock import MagicMock
import os
import io

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
    
    login_resp = await client.post("/login", data={
        "username": username,
        "password": password
    }, cookies=page_resp.cookies, headers=headers)
    
    return login_resp.cookies

@pytest.fixture
def setup_log_files(tmp_path):
    """
    配置 Mock 的 env_config_manager 并创建临时日志文件
    """
    # 1. 强制设置环境变量
    os.environ["LOG_DIR"] = str(tmp_path)
    
    # 2. Mock env_config_manager
    from utils.core.env_config import env_config_manager
    
    def get_config_side_effect(key, default=None):
        if key == "LOG_DIR":
            return str(tmp_path)
        return default
        
    if hasattr(env_config_manager, "get_config"):
        env_config_manager.get_config.side_effect = get_config_side_effect
    if hasattr(env_config_manager, "get_value"): # covering both
        env_config_manager.get_value.side_effect = get_config_side_effect

    # 3. Mock settings (if used)
    try:
        from core.config import settings
        if isinstance(settings, MagicMock):
            settings.LOG_DIR = str(tmp_path)
    except ImportError:
        pass
    
    # 4. 创建测试日志文件和目录
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    log1 = logs_dir / "app.log"
    log1.write_text("2026-01-01 12:00:00 INFO Test log entry 1\nLine 2\nLine 3", encoding="utf-8")
    
    log2 = logs_dir / "error.log"
    log2.write_text("Error message here", encoding="utf-8")
    
    # 也在根目录创建一份，防止应用读取的是 '.'
    (tmp_path / "app.log").write_text("2026-01-01 12:00:00 INFO Test log entry 1\nLine 2\nLine 3", encoding="utf-8")
    (tmp_path / "error.log").write_text("Error message here", encoding="utf-8")
    
    # 切换 CWD 到 tmp_path
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    # 如果应用使用 "logs" 目录
    # 我们将 Mock 返回 "logs"
    def get_config_side_effect_v2(key, default=None):
        if key == "LOG_DIR":
            return "logs" #Relative to CWD (tmp_path)
        return default

    if hasattr(env_config_manager, "get_config"):
        env_config_manager.get_config.side_effect = get_config_side_effect_v2
    
    yield tmp_path
    
    # 恢复 CWD
    os.chdir(original_cwd)

@pytest.mark.asyncio
async def test_list_log_files(client: AsyncClient, logs_auth_headers, setup_log_files):
    resp = await client.get("/api/logs/files", cookies=logs_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    
    files = data['data']
    filenames = [f['name'] for f in files]
    assert "app.log" in filenames
    assert "error.log" in filenames

@pytest.mark.asyncio
async def test_tail_log(client: AsyncClient, logs_auth_headers, setup_log_files):
    # Tail app.log
    resp = await client.get("/api/logs/tail?file=app.log&lines=10", cookies=logs_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    # data['data'] is a list of lines
    assert len(data['data']) > 0
    # assert any("Test log entry 1" in line for line in data['data'])

@pytest.mark.asyncio
async def test_download_log(client: AsyncClient, logs_auth_headers, setup_log_files):
    resp = await client.get("/api/logs/download?file=error.log", cookies=logs_auth_headers)
    assert resp.status_code == 200
    # 应该是文件流
    assert "Error message here" in resp.text
