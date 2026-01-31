from hypothesis import given, strategies as st
from core.helpers.time_range import format_time_range_display, parse_time_range_to_dates
from datetime import datetime, timezone
import pytest

@given(st.dictionaries(
    keys=st.sampled_from([
        "start_year", "start_month", "start_day", "start_hour", "start_minute", "start_second",
        "end_year", "end_month", "end_day", "end_hour", "end_minute", "end_second"
    ]),
    values=st.integers(min_value=-1000, max_value=10000)
))
def test_format_time_range_display_fuzz(time_range):
    # Should not crash
    result = format_time_range_display(time_range)
    assert isinstance(result, str)

@given(st.dictionaries(
    keys=st.sampled_from([
        "start_year", "start_month", "start_day", "start_hour", "start_minute", "start_second",
        "end_year", "end_month", "end_day", "end_hour", "end_minute", "end_second"
    ]),
    values=st.integers(min_value=-1000, max_value=10000)
))
def test_parse_time_range_to_dates_fuzz(time_range):
    # Should not crash
    begin_date, end_date, start_s, end_s = parse_time_range_to_dates(time_range)
    assert isinstance(begin_date, datetime)
    assert end_date is None or isinstance(end_date, datetime)
    assert isinstance(start_s, int)
    assert isinstance(end_s, int)

if __name__ == "__main__":
    test_format_time_range_display_fuzz()
    test_parse_time_range_to_dates_fuzz()
