import pytest
from httpx import AsyncClient, ASGITransport
from web_admin.fastapi_app import app

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

@pytest.mark.asyncio
async def test_csrf_protection_flow(db, clear_data):
    """
    Integration test for Global CSRF Protection.
    Task 2.3: CSRF Protection.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. 没有任何凭证的 POST 请求（应被拦截）
        response = await ac.post("/api/auth/login", data={"username": "admin", "password": "pw"})
        assert response.status_code == 403
        assert "CSRF" in response.text

        # 2. 访问 GET 页面获取 Cookie
        res_home = await ac.get("/")
        assert CSRF_COOKIE_NAME in res_home.cookies
        token = res_home.cookies[CSRF_COOKIE_NAME]

        # 3. 带 Cookie 但缺 Header 的 POST 请求（应被拦截）
        response = await ac.post("/api/auth/login", data={"username": "admin", "password": "pw"})
        assert response.status_code == 403

        # 4. 带正确 Cookie 和 Header 的请求
        # 注意：login 接口因为 Mock 可能会报 401 或者是 422 (由于 Depends 污染)
        # 但我们要验证的是 CSRF 拦截是否先于它们发生。
        # 如果返回不是 403，说明 CSRF 校验已通过。
        response = await ac.post("/api/auth/login", data={"username": "admin", "password": "pw"}, headers={CSRF_HEADER_NAME: token})
        assert response.status_code != 403
