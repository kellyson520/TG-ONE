import pytest
import datetime
from unittest.mock import MagicMock, patch

# Mock dependencies before importing SessionService
with patch("core.container.container"), \
     patch("core.helpers.tombstone.tombstone"), \
     patch("services.forward_settings_service.forward_settings_service"), \
     patch("services.dedup.engine.smart_deduplicator"):
    from services.session_service import SessionService

@pytest.fixture
def session_service():
    SessionService._instance = None
    service = SessionService()
    service.user_sessions = {}
    return service

@pytest.mark.asyncio
async def test_adjust_time_component_basic_wrapping(session_service):
    chat_id = 123
    tr = {
        "start_year": 2026,
        "start_month": 2,
        "start_day": 20,
        "start_hour": 10,
        "start_minute": 30,
        "start_second": 0
    }
    session_service.set_time_range(chat_id, tr)
    
    # Increase month
    await session_service.adjust_time_component(chat_id, "start", "month", 1)
    res = session_service.get_time_range(chat_id)
    assert res["start_month"] == 3
    
    # Decrease month from 1 to 12 (wrap, no year change)
    session_service.set_time_range(chat_id, {"start_month": 1, "start_year": 2026})
    await session_service.adjust_time_component(chat_id, "start", "month", -1)
    res = session_service.get_time_range(chat_id)
    assert res["start_month"] == 12
    assert res["start_year"] == 2026
    
    # Increase month from 12 to 1 (wrap, no year change)
    session_service.set_time_range(chat_id, {"start_month": 12, "start_year": 2026})
    await session_service.adjust_time_component(chat_id, "start", "month", 1)
    res = session_service.get_time_range(chat_id)
    assert res["start_month"] == 1
    assert res["start_year"] == 2026

@pytest.mark.asyncio
async def test_adjust_time_component_days_wrap(session_service):
    chat_id = 456
    # Feb 2024 (Leap year)
    session_service.set_time_range(chat_id, {
        "start_year": 2024,
        "start_month": 2,
        "start_day": 29
    })
    
    # +1 day -> 1 (Wrap within month)
    await session_service.adjust_time_component(chat_id, "start", "day", 1)
    assert session_service.get_time_range(chat_id)["start_day"] == 1
    assert session_service.get_time_range(chat_id)["start_month"] == 2

@pytest.mark.asyncio
async def test_adjust_time_component_time_wrap(session_service):
    chat_id = 789
    session_service.set_time_range(chat_id, {
        "start_hour": 23,
        "start_minute": 59,
        "start_second": 59
    })
    
    # +1 second -> 0 (Wrap)
    await session_service.adjust_time_component(chat_id, "start", "second", 1)
    res = session_service.get_time_range(chat_id)
    assert res["start_second"] == 0
    assert res["start_minute"] == 59 # stays same
