"""datetime_utils 测试 — 安全日期时间处理"""
import pytest
from datetime import datetime, timedelta
from core.helpers.datetime_utils import (
    safe_isoformat,
    safe_fromisoformat,
    get_current_isoformat,
    format_datetime_for_display,
    is_valid_datetime_string,
    safe_datetime_operation,
    add_days,
    subtract_days,
    get_age_in_days,
)


class TestSafeIsoformat:
    """safe_isoformat 测试"""

    def test_none_returns_none(self):
        assert safe_isoformat(None) is None

    def test_string_passthrough(self):
        assert safe_isoformat("2024-01-01T00:00:00") == "2024-01-01T00:00:00"

    def test_datetime_to_iso(self):
        dt = datetime(2024, 6, 15, 12, 30, 0)
        result = safe_isoformat(dt)
        assert "2024-06-15T12:30:00" in result

    def test_non_datetime_type(self):
        """非 datetime 类型转为字符串"""
        assert safe_isoformat(12345) == "12345"


class TestSafeFromisoformat:
    """safe_fromisoformat 测试"""

    def test_none_returns_none(self):
        assert safe_fromisoformat(None) is None

    def test_datetime_passthrough(self):
        dt = datetime(2024, 1, 1)
        assert safe_fromisoformat(dt) is dt

    def test_valid_iso_string(self):
        result = safe_fromisoformat("2024-06-15T12:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 6

    def test_invalid_string_returns_none(self):
        assert safe_fromisoformat("not-a-date") is None

    def test_unsupported_type_returns_none(self):
        assert safe_fromisoformat(12345) is None


class TestGetCurrentIsoformat:
    """get_current_isoformat 测试"""

    def test_returns_string(self):
        result = get_current_isoformat()
        assert isinstance(result, str)

    def test_contains_t_separator(self):
        result = get_current_isoformat()
        assert "T" in result


class TestFormatDatetimeForDisplay:
    """format_datetime_for_display 测试"""

    def test_none_returns_unknown(self):
        assert format_datetime_for_display(None) == "未知"

    def test_invalid_string_returns_invalid(self):
        assert format_datetime_for_display("not-a-date") == "无效日期"

    def test_datetime_formatted(self):
        dt = datetime(2024, 6, 15, 12, 30, 0)
        result = format_datetime_for_display(dt)
        assert result == "2024-06-15 12:30:00"

    def test_iso_string_formatted(self):
        result = format_datetime_for_display("2024-06-15T12:30:00")
        assert result == "2024-06-15 12:30:00"

    def test_custom_format(self):
        dt = datetime(2024, 6, 15)
        result = format_datetime_for_display(dt, "%Y/%m/%d")
        assert result == "2024/06/15"


class TestIsValidDatetimeString:
    """is_valid_datetime_string 测试"""

    def test_valid_iso(self):
        assert is_valid_datetime_string("2024-06-15T12:30:00") is True

    def test_valid_date(self):
        assert is_valid_datetime_string("2024-06-15") is True

    def test_invalid_string(self):
        assert is_valid_datetime_string("not-a-date") is False

    def test_non_string(self):
        assert is_valid_datetime_string(12345) is False

    def test_empty_string(self):
        assert is_valid_datetime_string("") is False


class TestSafeDatetimeOperation:
    """safe_datetime_operation 测试"""

    def test_none_returns_none(self):
        assert safe_datetime_operation(None, lambda dt: dt) is None

    def test_returns_iso_string(self):
        dt = datetime(2024, 1, 1)
        result = safe_datetime_operation(dt, lambda dt: dt + timedelta(days=1))
        assert "2024-01-02" in result

    def test_operation_error_returns_none(self):
        dt = datetime(2024, 1, 1)
        result = safe_datetime_operation(dt, lambda dt: 1 / 0)
        assert result is None

    def test_string_input(self):
        result = safe_datetime_operation("2024-01-01T00:00:00", lambda dt: dt + timedelta(hours=1))
        assert "01:00:00" in result


class TestAddDays:
    """add_days 测试"""

    def test_add_positive_days(self):
        result = add_days("2024-01-01T00:00:00", 5)
        assert "2024-01-06" in result

    def test_add_zero_days(self):
        result = add_days("2024-01-01T00:00:00", 0)
        assert "2024-01-01" in result

    def test_none_returns_none(self):
        assert add_days(None, 5) is None


class TestSubtractDays:
    """subtract_days 测试"""

    def test_subtract_days(self):
        result = subtract_days("2024-01-10T00:00:00", 5)
        assert "2024-01-05" in result

    def test_none_returns_none(self):
        assert subtract_days(None, 5) is None


class TestGetAgeInDays:
    """get_age_in_days 测试"""

    def test_returns_int(self):
        result = get_age_in_days("2020-01-01T00:00:00")
        assert isinstance(result, int)
        assert result > 0

    def test_none_returns_none(self):
        assert get_age_in_days(None) is None

    def test_recent_date(self):
        now = datetime.utcnow()
        result = get_age_in_days(now.isoformat())
        assert result == 0
