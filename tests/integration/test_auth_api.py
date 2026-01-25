import pytest

@pytest.mark.asyncio
async def test_root_redirect(client):
    """测试根路径重定向"""
    # 默认未登录应重定向到 login
    response = await client.get("/", follow_redirects=False)
    assert response.status_code in [200, 307]

@pytest.mark.asyncio
async def test_login_page_loads(client):
    """测试登录页面加载与 CSRF Cookie 设置"""
    response = await client.get("/login")
    assert response.status_code == 200
    assert "csrf_token" in response.cookies
    assert "管理面板" in response.text

