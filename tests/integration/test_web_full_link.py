
import pytest
import datetime
from sqlalchemy import select
from services.authentication_service import authentication_service
from models.models import ForwardRule, RuleLog, Chat, User

@pytest.mark.asyncio
async def test_web_full_link_rule_cycle(client, db):
    """
    Scenario A: Rule Config Cycle
    Web Create -> DB Verify -> Mock Handler -> Web Verify Log
    """
    from web_admin.security.deps import get_current_user, admin_required
    
    # Mock User
    mock_user = User(id=1, username="admin", is_admin=True)
    
    # Override Dependency
    # We need to access the app instance. Tests usually use 'client' which accesses 'app' via 'get_app()' in conftest.
    # conftest 'client' fixture:
    #   app = get_app()
    #   transport = ASGITransport(app=app)
    #   async with AsyncClient(...)
    
    # We need to override ON THE APP that CLIENT uses.
    from tests.conftest import get_app
    app = get_app()
    app.dependency_overrides[admin_required] = lambda: mock_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    # CSRF Token Mock (Still needed for middleware)
    csrf_token = "dummy_csrf_token"
    headers = {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}" # Middleware reads cookie 'csrf_token'
    }

    
    # 2. Web: Create Rule (POST /api/forward_rules/)
    # Check rule_router prefix. Usually /api/forward_rules or similar. 
    # rule_router.py shows prefix="/api/rules"
    
    rule_data = {
        "source_chat_id": "100",
        "target_chat_id": "200",
        "enabled": True
    }
    
    # Pre-create Chats (Repository constraint)

    chat_src = Chat(id=100, telegram_chat_id=100, name="Src", chat_type="group")
    chat_tgt = Chat(id=200, telegram_chat_id=200, name="Tgt", chat_type="group")
    db.add(chat_src)
    db.add(chat_tgt)
    await db.commit()
    
    resp = await client.post("/api/rules", json=rule_data, headers=headers)
    assert resp.status_code == 200, f"Create Rule failed: {resp.text}"
    data = resp.json()
    assert data["success"] == True, f"Response: {data}"
    rule_id = data["rule_id"]
    
    # 3. Store: Verify DB
    # We use the 'db' fixture to query directly
    # Need to commit? The API likely committed.
    stmt = select(ForwardRule).where(ForwardRule.id == rule_id)
    result = await db.execute(stmt)
    rule_db = result.scalar_one_or_none()
    assert rule_db is not None
    assert rule_db.target_chat_id == 200
    
    # 4. Mock Action/Log Generation
    # Simulate the system processing a message and creating a RuleLog
    # In a real full E2E, we'd fire a webhook. Since webhook param is missing in router list (maybe in main.py?),
    # We will manually insert a Log to simulate the "Callback/Effect" part, 
    # then verify Web API can see it.
    
    log = RuleLog(
        rule_id=rule_id,
        action="forward",
        source_message_id=999,
        result="success",
        processing_time=123
    )
    db.add(log)
    await db.commit()
    
    # 5. Web: Fetch Log
    # Assuming there's a logs router. Check routers list -> logs_router? 
    # Previous ls didn't show logs_router.py? 
    # Wait, 'ls web_admin/routers' showed: auth, rule, user. 
    # Ah, 'test_logs_api.py' exists in tests! This implies there IS a logs API.
    # Maybe it's defined in main.py or another file?
    # Or maybe I missed it in 'ls'.
    # Let's assume /api/logs/ or similar.
    # Attempt to fetch rule logs
    
    # If the logs router is missing, we fail this step, but helpful to know.
    # Let's try to query rule details again, maybe it includes stats?
    
    # 6. Web: Verify Rule State (GET /api/rules)
    # GET /api/rules endpoint returns list of rules
    resp_list = await client.get("/api/rules", params={"page": 1, "size": 100}, headers=headers)
    assert resp_list.status_code == 200
    rules_data = resp_list.json()["data"]["items"]
    found_rule = next((r for r in rules_data if r["id"] == rule_id), None)
    assert found_rule is not None
    
    # instead, we verify we can Update the rule via Web.
    
    update_data = {"enabled": False}
    resp_update = await client.put(f"/api/rules/{rule_id}", json=update_data, headers=headers)
    assert resp_update.status_code == 200, f"Update Rule failed: {resp_update.text}"
    assert resp_update.json()["success"] == True
    
    # Verify DB again
    await db.commit() # Commit to end current transaction and see changes from API
    db.expire_all()
    # Re-query explicitly to ensure we get fresh data from DB
    stmt = select(ForwardRule).where(ForwardRule.id == rule_id)
    result = await db.execute(stmt)
    rule_final = result.scalar_one()
    
    assert rule_final.enable_rule == False

    # 5. Simulate Log Generation
    processed_log = RuleLog(
        rule_id=rule_id,
        action="forward",
        source_message_id=12345,
        result="success"
    )
    db.add(processed_log)
    await db.commit()
    
    # 6. Verify Log via Web API
    resp_logs = await client.get(f"/api/rules/logs?rule_id={rule_id}", headers=headers)
    assert resp_logs.status_code == 200
    logs_data = resp_logs.json()["data"]["items"]
    assert len(logs_data) >= 1
    # Check most recent log
    assert logs_data[0]["source_message_id"] == 12345
    assert logs_data[0]["action"] == "forward"


