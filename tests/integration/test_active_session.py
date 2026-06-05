import pytest
from services.authentication_service import authentication_service
from services.active_session_service import active_session_service
from models.models import User

@pytest.mark.asyncio
async def test_session_management(db, clear_data):
    """
    Integration test for ActiveSessionService.
    Task 2.2: Session Management & Device Parsing.
    """
    # 1. Create User
    user = User(username="admin", password="pw", is_active=True, is_admin=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 2. Create Sessions with different UAs
    # Note: werkzeug parser might need specific exact strings to work well.
    ua_pc = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ua_mobile = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
    
    token1, _ = await authentication_service.create_session(user.id, "1.1.1.1", ua_pc)
    token2, _ = await authentication_service.create_session(user.id, "2.2.2.2", ua_mobile)
    
    # 3. List Sessions
    sessions = await active_session_service.get_all_sessions(user_id=user.id)
    assert len(sessions) == 2
    
    # Verify Device Parsing
    # Order desc by created_at. So token2 (mobile) should be first (index 0).
    s1 = sessions[0] # Mobile
    s2 = sessions[1] # PC
    
    # Check if Parsing worked
    print(f"DEBUG: S1 Device Info: {s1['device_info']}")
    print(f"DEBUG: S2 Device Info: {s2['device_info']}")

    assert s1["device_info"] != "Unknown Device"
    # werkzeug UserAgent usually returns platform/browser
    # Check flexible
    
    assert s2["device_info"] != "Unknown Device"
    assert "windows" in s2["device_info"].lower()

    # 4. Revoke One Session
    target_id = s1["id"]
    success = await active_session_service.revoke_session(target_id)
    assert success is True
    
    # Verify gone
    sessions_after = await active_session_service.get_all_sessions(user_id=user.id)
    assert len(sessions_after) == 1
    assert sessions_after[0]["id"] == s2["id"]
