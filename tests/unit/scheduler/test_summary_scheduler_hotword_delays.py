from datetime import datetime

import pytz

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
