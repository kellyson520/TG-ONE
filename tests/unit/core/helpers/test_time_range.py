from datetime import datetime, timezone

from core.helpers.time_range import (
    format_time_range_display,
    parse_time_range_to_dates,
)


def test_format_time_range_display_treats_malformed_values_as_zero(caplog):
    time_range = {
        "start_year": "bad",
        "start_month": object(),
        "start_day": "",
        "start_hour": "not-hour",
        "start_minute": None,
        "start_second": [],
        "end_year": {},
        "end_month": "nan",
        "end_day": object(),
        "end_hour": "oops",
        "end_minute": object(),
        "end_second": "bad",
    }

    assert format_time_range_display(time_range) == "全部时间 (将获取全部消息)"
    assert "Invalid time range component start_year" in caplog.text
    assert "Invalid time range component end_second" in caplog.text


def test_parse_time_range_to_dates_treats_malformed_clock_values_as_zero(caplog):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    time_range = {
        "start_hour": "bad",
        "start_minute": object(),
        "start_second": [],
        "end_hour": {},
        "end_minute": "bad",
        "end_second": object(),
    }

    begin_date, end_date, start_s, end_s = parse_time_range_to_dates(time_range, now)

    assert begin_date == datetime(2010, 1, 1, tzinfo=timezone.utc)
    assert end_date is None
    assert start_s == 0
    assert end_s == 0
    assert "Invalid time range component start_minute" in caplog.text
    assert "Invalid time range component end_second" in caplog.text
