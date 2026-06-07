from datetime import datetime

import pytz
import pytest

from scheduler import summary_scheduler as scheduler_module


def _scheduler_at(monkeypatch, fixed_now):
    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(scheduler_module, "datetime", FixedDateTime)
    scheduler = scheduler_module.SummaryScheduler.__new__(scheduler_module.SummaryScheduler)
    scheduler.timezone = fixed_now.tzinfo
    return scheduler


def test_hotword_monthly_delay_targets_next_calendar_month(monkeypatch):
    tz = pytz.timezone("Asia/Shanghai")
    fixed_now = tz.localize(datetime(2026, 1, 31, 2, 0, 0))
    scheduler = _scheduler_at(monkeypatch, fixed_now)

    delay = scheduler._seconds_until_next_monthly(1, 0, 0)

    expected = tz.localize(datetime(2026, 2, 1, 1, 0, 0)) - fixed_now
    assert delay == expected.total_seconds()


def test_hotword_yearly_delay_targets_next_calendar_year(monkeypatch):
    tz = pytz.timezone("Asia/Shanghai")
    fixed_now = tz.localize(datetime(2026, 12, 31, 3, 0, 0))
    scheduler = _scheduler_at(monkeypatch, fixed_now)

    delay = scheduler._seconds_until_next_yearly(2, 0, 0)

    expected = tz.localize(datetime(2027, 1, 1, 2, 0, 0)) - fixed_now
    assert delay == expected.total_seconds()


def test_summary_scheduler_uses_configured_timezone(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "TIMEZONE", "UTC", raising=False)
    monkeypatch.setattr(scheduler_module, "get_message_handler", lambda _client: object())
    monkeypatch.setattr(scheduler_module, "get_smart_cache", lambda *_args, **_kwargs: object())

    scheduler = scheduler_module.SummaryScheduler(None, None, None, None)

    assert str(scheduler.timezone) == "UTC"


@pytest.mark.asyncio
async def test_hotword_startup_catches_up_closed_monthly_and_yearly_rollups(monkeypatch):
    tz = pytz.timezone("Asia/Shanghai")
    fixed_now = tz.localize(datetime(2026, 1, 1, 2, 30, 0))
    scheduler = _scheduler_at(monkeypatch, fixed_now)

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return FakeResult()

    class FakeDb:
        def get_session(self):
            return FakeSession()

    class FakeTimingWheel:
        def __init__(self):
            self.tasks = []
            self.started = False

        def add_task(self, task_id, delay_seconds, callback, *args):
            self.tasks.append((task_id, delay_seconds, callback, args))

        async def start(self):
            self.started = True

    class FakeHotwordService:
        def __init__(self):
            self.monthly_calls = 0
            self.yearly_calls = 0

        async def aggregate_monthly(self):
            self.monthly_calls += 1

        async def aggregate_yearly(self):
            self.yearly_calls += 1

    fake_service = FakeHotwordService()
    import services.hotword_service as hotword_service_module

    monkeypatch.setattr(scheduler_module.settings, "ENABLE_HOTWORD", True, raising=False)
    monkeypatch.setattr(hotword_service_module, "get_hotword_service", lambda: fake_service)

    scheduler.tasks = {}
    scheduler.db = FakeDb()
    scheduler.timing_wheel = FakeTimingWheel()

    await scheduler.start()

    assert fake_service.monthly_calls == 1
    assert fake_service.yearly_calls == 1
    assert scheduler.timing_wheel.started is True
