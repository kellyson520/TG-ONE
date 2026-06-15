import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import rss_pull_service as rss_module
from services.rss_pull_service import RSSPullService


class FakeTimingWheel:
    def __init__(self):
        self.calls = []

    def add_task(self, task_id, delay_seconds, callback, **kwargs):
        self.calls.append(
            {
                "task_id": task_id,
                "delay_seconds": delay_seconds,
                "callback": callback,
                "kwargs": kwargs,
            }
        )
        return task_id


class FakeSession:
    def __init__(self, sub):
        self.sub = sub
        self.commits = 0

    async def get(self, model, sub_id):
        return self.sub if self.sub.id == sub_id else None

    async def commit(self):
        self.commits += 1


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeDB:
    def __init__(self, session):
        self.session = session

    def get_session(self):
        return FakeSessionContext(self.session)


def make_subscription(**overrides):
    values = {
        "id": 7,
        "is_active": True,
        "min_interval": 10,
        "max_interval": 300,
        "current_interval": 15,
        "last_checked": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_schedule_subscription_uses_timing_wheel_seconds_api():
    service = RSSPullService(user_client=None, bot_client=None)
    service.timing_wheel = FakeTimingWheel()
    sub = make_subscription()

    await service.schedule_subscription(sub)

    assert service.timing_wheel.calls == [
        {
            "task_id": "rss_pull_7",
            "delay_seconds": 15,
            "callback": service.pull_task,
            "kwargs": {"sub_id": 7},
        }
    ]


@pytest.mark.asyncio
async def test_pull_error_reschedules_without_sleep(monkeypatch):
    service = RSSPullService(user_client=None, bot_client=None)
    service._running = True
    service.timing_wheel = FakeTimingWheel()
    sub = make_subscription(current_interval=20)
    session = FakeSession(sub)
    service.set_db(FakeDB(session))
    sleep_calls = []

    async def fail_sleep(delay):
        sleep_calls.append(delay)
        raise AssertionError(f"RSS pull error path slept instead of rescheduling: {delay}")

    monkeypatch.setattr(rss_module.asyncio, "sleep", fail_sleep)
    service._do_pull = AsyncMock(side_effect=RuntimeError("network down"))

    await service.pull_task(sub.id)

    assert sleep_calls == []
    assert service.timing_wheel.calls[-1]["task_id"] == "rss_pull_7"
    assert service.timing_wheel.calls[-1]["delay_seconds"] == 60
