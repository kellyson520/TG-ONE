"""time_range 测试 — 时间范围解析与格式化"""
import pytest
from datetime import datetime, timezone
from core.helpers.time_range import (
    clamp_time_component,
    format_time_range_display,
    parse_time_range_to_dates,
)


class TestClampTimeComponent:
    """clamp_time_component 约束测试"""

    def test_year_clamped_to_zero(self):
        assert clamp_time_component(-1, "year") == 0

    def test_year_normal(self):
        assert clamp_time_component(2024, "year") == 2024

    def test_month_clamped_to_12(self):
        assert clamp_time_component(13, "month") == 12

    def test_month_clamped_to_zero(self):
        assert clamp_time_component(-1, "month") == 0

    def test_month_normal(self):
        assert clamp_time_component(6, "month") == 6

    def test_day_clamped_to_31(self):
        assert clamp_time_component(32, "day") == 31

    def test_day_clamped_to_zero(self):
        assert clamp_time_component(-5, "day") == 0

    def test_seconds_no_upper_bound(self):
        assert clamp_time_component(86400, "seconds") == 86400

    def test_seconds_clamped_to_zero(self):
        assert clamp_time_component(-1, "seconds") == 0

    def test_none_returns_zero(self):
        assert clamp_time_component(None, "year") == 0

    def test_string_number(self):
        assert clamp_time_component("5", "month") == 5

    def test_invalid_string_returns_zero(self):
        assert clamp_time_component("abc", "day") == 0


class TestFormatTimeRangeDisplay:
    """format_time_range_display 格式化测试"""

    def test_all_zeros_returns_all(self):
        result = format_time_range_display({})
        assert result == "全部时间 (将获取全部消息)"

    def test_start_only(self):
        result = format_time_range_display({
            "start_year": 2024, "start_month": 6, "start_day": 15
        })
        assert "2024年" in result
        assert "6月" in result
        assert "15天" in result

    def test_time_range_with_hours(self):
        result = format_time_range_display({
            "start_hour": 9, "start_minute": 30,
            "end_hour": 18, "end_minute": 0,
        })
        assert "09:30:00" in result
        assert "18:00:00" in result

    def test_end_zero_shows_infinity(self):
        result = format_time_range_display({
            "start_hour": 8, "start_minute": 0,
        })
        assert "∞" in result

    def test_partial_date_no_day(self):
        result = format_time_range_display({
            "start_year": 2024, "start_month": 3
        })
        assert "2024年" in result
        assert "3月" in result

    def test_start_unlimited(self):
        """只有结束时间，开始不限"""
        result = format_time_range_display({
            "end_hour": 23, "end_minute": 59,
        })
        assert "23:59:00" in result


class TestParseTimeRangeToDates:
    """parse_time_range_to_dates 解析测试"""

    def test_all_zeros_default_dates(self):
        """全零 → begin_date=2010-01-01, end_date=None"""
        begin, end, start_s, end_s = parse_time_range_to_dates({})
        assert begin == datetime(2010, 1, 1, tzinfo=timezone.utc)
        assert end is None
        assert start_s == 0
        assert end_s == 0

    def test_full_date_range(self):
        """完整日期范围"""
        tr = {
            "start_year": 2024, "start_month": 1, "start_day": 1,
            "end_year": 2024, "end_month": 12, "end_day": 31,
        }
        begin, end, start_s, end_s = parse_time_range_to_dates(tr)
        assert begin == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert end == datetime(2024, 12, 31, tzinfo=timezone.utc)

    def test_relative_days(self):
        """天数 → 相对日期"""
        now = datetime(2024, 6, 15, tzinfo=timezone.utc)
        tr = {"start_day": 7}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr, now=now)
        assert begin.year == 2024
        assert begin.month == 6
        assert begin.day == 8  # 15 - 7

    def test_year_only(self):
        """只有年份 → 该年1月1日"""
        now = datetime(2024, 6, 15, tzinfo=timezone.utc)
        tr = {"start_year": 2023}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr, now=now)
        assert begin == datetime(2023, 1, 1, tzinfo=timezone.utc)

    def test_end_year_only(self):
        """只有结束年份 → 该年12月31日23:59:59"""
        tr = {"end_year": 2024}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr)
        assert end is not None
        assert end.year == 2024
        assert end.month == 12
        assert end.day == 31

    def test_end_year_month(self):
        """结束年+月 → 该月最后一天"""
        tr = {"end_year": 2024, "end_month": 2}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr)
        assert end is not None
        assert end.month == 2
        assert end.day == 29  # 2024 是闰年

    def test_start_seconds_computed(self):
        """start_hour/minute/second → start_s"""
        tr = {"start_hour": 2, "start_minute": 30, "start_second": 15}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr)
        assert start_s == 2 * 3600 + 30 * 60 + 15

    def test_end_seconds_computed(self):
        """end_hour/minute/second → end_s"""
        tr = {"end_hour": 18, "end_minute": 0, "end_second": 0}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr)
        assert end_s == 18 * 3600

    def test_invalid_date_fallback(self):
        """无效日期回退到默认"""
        now = datetime(2024, 6, 15, tzinfo=timezone.utc)
        tr = {"start_year": 2024, "start_month": 13, "start_day": 32}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr, now=now)
        # 月份13被clamp到12，日期32被clamp到31 → 有效日期
        assert begin.month == 12
        assert begin.day == 31

    def test_start_s_wraps_at_86400(self):
        """start_s 模 86400"""
        tr = {"start_hour": 25, "start_minute": 0}
        begin, end, start_s, end_s = parse_time_range_to_dates(tr)
        # 25小时 = 90000 > 86400, 但 seconds 被 clamp 为 max(0,v)=90000
        # start_s = ss % 86400 = 3600
        assert start_s == 3600
