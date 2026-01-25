import pytest
from httpx import AsyncClient
from unittest.mock import patch
from models.models import User
import os
import asyncio

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestAuthRouter:
    @pytest.fixture(autouse=True)
    def setup_env(self):
        os.environ["COOKIE_SECURE"] = "false"
        yield
        if "COOKIE_SECURE" in os.environ:
            del os.environ["COOKIE_SECURE"]

    async def get_csrf(self, client: AsyncClient):
        # 使用根路径获取 CSRF，注意由于没有登录可能会 401，但 CSRF Cookie 应该会带回
        resp = await client.get("/")
        return resp.cookies.get("csrf_token")

    async def test_login_success(self, client: AsyncClient, db):
        csrf = await self.get_csrf(client)
        # 1. 准备用户
        from werkzeug.security import generate_password_hash
        user = User(
            username="testuser", 
            password=generate_password_hash("password123"),
            is_active=True
        )
        db.add(user)
        await db.commit()
        
        # 2. 登录请求
        login_data = {"username": "testuser", "password": "password123"}
        resp = await client.post("/api/auth/login", json=login_data, headers={"X-CSRF-Token": csrf or ""})
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data
        # 验证返回了令牌

    async def test_login_invalid_credentials(self, client: AsyncClient, db):
        csrf = await self.get_csrf(client)
        login_data = {"username": "wrong", "password": "wrong"}
        resp = await client.post("/api/auth/login", json=login_data, headers={"X-CSRF-Token": csrf or ""})
        
        assert resp.status_code == 401

    async def test_register_flow(self, client: AsyncClient, db):
        csrf = await self.get_csrf(client)
        with patch("services.system_service.system_service.get_allow_registration", return_value=True):
            reg_data = {"username": "newuser", "password": "Password123!"}
            resp = await client.post("/api/auth/register", data=reg_data, headers={"X-CSRF-Token": csrf or ""})
            
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    async def test_logout(self, client: AsyncClient):
        csrf = await self.get_csrf(client)
        resp = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf or ""})
        assert resp.status_code == 200

    async def test_refresh_token(self, client: AsyncClient, db):
        # 1. 创建真实会话 (通过登录)
        from werkzeug.security import generate_password_hash
        user = User(username="refuser", password=generate_password_hash("pass"), is_active=True)
        db.add(user)
        await db.commit()
        
        login_resp = await client.post("/api/auth/login", json={"username": "refuser", "password": "pass"})
        refresh_token = login_resp.json()["refresh_token"]
        current_csrf = login_resp.cookies.get("csrf_token")
        
        await asyncio.sleep(1.1)
        
        # 2. 调用刷新
        resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token}, headers={"X-CSRF-Token": current_csrf or ""})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
