import pytest
from httpx import AsyncClient
from models.models import User, Chat, ForwardRule
from web_admin.fastapi_app import _issue_token

@pytest.mark.asyncio
class TestRuleApi:
    async def test_get_rules_unauthorized(self, client: AsyncClient):
        # 未登录请求
        response = await client.get("/api/rules")
        assert response.status_code == 401

    async def test_get_rules_authorized(self, client: AsyncClient, db):
        # 1. 创建用户并签发 Token
        user = User(username="testadmin", password="hashed_password", is_admin=True)
        db.add(user)
        
        # 2. 创建一些测试规则
        c1 = Chat(telegram_chat_id="-1001", name="Source")
        c2 = Chat(telegram_chat_id="-1002", name="Target")
        db.add_all([c1, c2])
        await db.flush()
        
        rule = ForwardRule(source_chat_id=c1.id, target_chat_id=c2.id)
        db.add(rule)
        await db.commit()
        
        token = _issue_token(user.id)
        
        # 1. 模拟 CSRF Token
        csrf_token = "test_csrf_token"
        client.cookies.set("access_token", token)
        client.cookies.set("csrf_token", csrf_token)
        
        # 3. 发起请求
        response = await client.get("/api/rules", headers={"X-CSRF-Token": csrf_token})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["source_chat"]["telegram_chat_id"] == "-1001"

    async def test_delete_rule_admin_required(self, client: AsyncClient, db):
        # 非管理员尝试删除
        user = User(username="normaluser", password="hashed_password", is_admin=False)
        db.add(user)
        await db.commit()
        
        token = _issue_token(user.id)
        
        csrf_token = "test_csrf_token"
        client.cookies.set("access_token", token)
        client.cookies.set("csrf_token", csrf_token)
        
        # DELETE 是敏感操作，触发 CSRF 检查
        response = await client.delete("/api/rules/1", headers={"X-CSRF-Token": csrf_token})
        # 因为 admin_required 里面调用了 Depends(login_required)
        # 如果 user.is_admin 为 False，它会尝试返回 RedirectResponse("/") (Web) 或 403 (API)
        # 根据代码：if request.url.path.startswith('/api/'): raise HTTPException(403)
        assert response.status_code == 403
