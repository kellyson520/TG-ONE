import pytest
from httpx import AsyncClient
import secrets
from werkzeug.security import generate_password_hash as get_password_hash
from core.container import container
from models.models import User, AuditLog
from datetime import datetime

@pytest.fixture
async def admin_auth_headers(client: AsyncClient):
    """
    创建一个管理员用户并登录，返回包含 CSRF Token 和 Cookie 的 Headers/Cookies
    """
    # 1. 创建管理员
    username = f"admin_audit_{secrets.token_hex(4)}"
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
        user_id = admin_user.id

    # 2. 获取 CSRF Token
    page_resp = await client.get("/login")
    csrf_token = page_resp.cookies.get("csrf_token")
    
    # 3. 登录
    login_headers = {"X-CSRF-Token": csrf_token, "Accept": "application/json"}
    login_resp = await client.post("/login", data={
        "username": username,
        "password": password
    }, cookies=page_resp.cookies, headers=login_headers)
    
    assert login_resp.status_code == 200
    
    return {
        "cookies": login_resp.cookies,
        "user_id": user_id,
        "username": username
    }

import json

@pytest.fixture
async def seed_audit_logs(admin_auth_headers):
    """
    预置一些审计日志数据
    """
    try:
        user_id = admin_auth_headers["user_id"]
        username = admin_auth_headers["username"]
        
        logs = [
            AuditLog(user_id=user_id, username=username, action="LOGIN", ip_address="127.0.0.1", status="success", details=json.dumps({"method": "web"})),
            AuditLog(user_id=user_id, username=username, action="UPDATE_RULE", ip_address="127.0.0.1", status="success", details=json.dumps({"rule_id": 1})),
            AuditLog(user_id=user_id, username=username, action="DELETE_USER", ip_address="127.0.0.1", status="failure", details=json.dumps({"target_uid": 999})),
        ]
        
        async with container.db.session() as session:
            session.add_all(logs)
            await session.commit()
            
        return logs
    except Exception as e:
        print(f"Fixture seed_audit_logs failed: {e}")
        import traceback
        traceback.print_exc()
        raise e

@pytest.mark.asyncio
async def test_get_audit_logs(client: AsyncClient, admin_auth_headers, seed_audit_logs):
    cookies = admin_auth_headers["cookies"]
    
    # 1. 无参数查询 (默认分页)
    resp = await client.get("/api/system/audit/logs", cookies=cookies)
    if resp.status_code != 200:
        raise Exception(f"API Error {resp.status_code}: {resp.text}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]["logs"]) >= 3
    assert data["data"]["page"] == 1
    assert data["data"]["limit"] == 50

    # 2. 按 Action 筛选
    resp = await client.get("/api/system/audit/logs?action=LOGIN", cookies=cookies)
    data = resp.json()
    assert len(data["data"]["logs"]) >= 1
    assert all(log["action"] == "LOGIN" for log in data["data"]["logs"])

    # 3. 按 User ID 筛选
    uid = admin_auth_headers["user_id"]
    resp = await client.get(f"/api/system/audit/logs?user_id={uid}", cookies=cookies)
    data = resp.json()
    # 应该包含我们插入的所有日志 (因为都是这个用户产生的)
    assert len(data["data"]["logs"]) >= 3
    
    # 4. 分页测试
    resp = await client.get("/api/system/audit/logs?page=1&limit=1", cookies=cookies)
    data = resp.json()
    assert len(data["data"]["logs"]) == 1
    
    resp = await client.get("/api/system/audit/logs?page=2&limit=1", cookies=cookies)
    data2 = resp.json()
    assert len(data2["data"]["logs"]) == 1
    assert data["data"]["logs"][0]["id"] != data2["data"]["logs"][0]["id"]

@pytest.mark.asyncio
async def test_audit_logs_unauthorized(client: AsyncClient):
    # 未登录访问
    resp = await client.get("/api/system/audit/logs")
    assert resp.status_code in [401, 403]

@pytest.mark.asyncio
async def test_audit_logs_forbidden(client: AsyncClient):
    # 普通用户访问 (非管理员)
    # 1. 创建普通用户
    username = f"user_{secrets.token_hex(4)}"
    password = "password123"
    user = User(username=username, password=get_password_hash(password), is_admin=False)
    
    async with container.db.session() as session:
        session.add(user)
        await session.commit()
    
    # 2. 登录
    page_resp = await client.get("/login")
    csrf_token = page_resp.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_token, "Accept": "application/json"}
    
    login_resp = await client.post("/login", data={
        "username": username,
        "password": password
    }, cookies=page_resp.cookies, headers=headers)
    
    # 3. 尝试访问审计日志
    resp = await client.get("/api/system/audit/logs", cookies=login_resp.cookies)
    assert resp.status_code in [401, 403]
