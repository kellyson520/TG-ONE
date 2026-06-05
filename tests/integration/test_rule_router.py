import pytest
from httpx import AsyncClient
from models.models import Chat, User, ForwardRule

@pytest.fixture
async def auth_headers(client: AsyncClient, db):
    # 为测试准备管理员权限的 headers
    from web_admin.security.deps import admin_required, login_required
    from tests.conftest import get_app
    
    mock_user = User(id=1, username="admin", is_admin=True)
    app = get_app()
    app.dependency_overrides[admin_required] = lambda: mock_user
    app.dependency_overrides[login_required] = lambda: mock_user
    
    csrf_token = "test_csrf_rule"
    headers = {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}"
    }
    yield headers
    app.dependency_overrides = {}

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
async def test_rule_crud_flow(client, auth_headers, db):
    # 1. 准备 Chat 数据 (Repository 需要关联 Chat)
    c1 = Chat(id=101, telegram_chat_id="-101", name="Source", type="supergroup")
    c2 = Chat(id=102, telegram_chat_id="-102", name="Target", type="supergroup")
    db.add_all([c1, c2])
    await db.commit()
    
    # 2. 创建规则
    rule_data = {
        "source_chat_id": "-101",
        "target_chat_id": "-102",
        "enabled": True
    }
    resp = await client.post("/api/rules", json=rule_data, headers=auth_headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    rule_id = res["data"]["rule_id"]
    
    # 3. 验证列表显示
    resp = await client.get("/api/rules", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["id"] == rule_id for r in data["data"]["items"])
    
    # 4. 更新规则
    update_data = {"enabled": False, "description": "Updated Desc"}
    resp = await client.put(f"/api/rules/{rule_id}", json=update_data, headers=auth_headers)
    assert resp.status_code == 200
    
    # 验证 DB 更新
    await db.commit() # 等待刚才的 API 操作落地
    from sqlalchemy import select
    stmt = select(ForwardRule).where(ForwardRule.id == rule_id)
    res = await db.execute(stmt)
    rule = res.scalar_one()
    assert rule.enable_rule is False
    assert rule.description == "Updated Desc"
    
    # 5. 添加关键词
    kw_data = {"keywords": ["alert", "error"], "is_regex": False}
    resp = await client.post(f"/api/rules/{rule_id}/keywords", json=kw_data, headers=auth_headers)
    assert resp.status_code == 200
    
    # 6. 删除规则
    resp = await client.delete(f"/api/rules/{rule_id}", headers=auth_headers)
    assert resp.status_code == 200
    
    # 验证已删除
    db.expire_all()
    res = await db.execute(stmt)
    assert res.scalar_one_or_none() is None
