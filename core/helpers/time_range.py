"""时间范围与时间选择相关的公共函数"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from typing import Dict, Optional, Tuple


def clamp_time_component(value: int, unit: str) -> int:
    """约束时间分量到合法范围。
    unit: 'year' | 'month' | 'day' | 'seconds'
    """
    try:
        v = int(value or 0)
    except Exception:
        v = 0
    if unit == "year":
        return max(0, v)
    if unit == "month":
        return max(0, min(12, v))
    if unit == "day":
        return max(0, min(31, v))
    if unit == "seconds":
        return max(0, v)
    return v


def format_time_range_display(time_range: Dict[str, int]) -> str:
    """格式化时间范围显示文本（与历史/会话时间范围展示一致）。
    期望字段：start_year/start_month/start_day/start_hour/start_minute/start_second
            end_year/end_month/end_day/end_hour/end_minute/end_second
    若无，则视为 0。
    """

    def fmt_time(sec: int) -> str:
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def fmt_date(year: int, month: int, day: int) -> str:
        parts = []
        if year > 0:
            parts.append(f"{year}年")
        if month > 0:
            parts.append(f"{month}月")
        if day > 0:
            parts.append(f"{day}天")
        return "".join(parts) if parts else "不限"

    sy = int(time_range.get("start_year", 0) or 0)
    sm = int(time_range.get("start_month", 0) or 0)
    sd = int(time_range.get("start_day", 0) or 0)
    sh = int(time_range.get("start_hour", 0) or 0)
    smin = int(time_range.get("start_minute", 0) or 0)
    ss = int(time_range.get("start_second", 0) or 0)
    ey = int(time_range.get("end_year", 0) or 0)
    em = int(time_range.get("end_month", 0) or 0)
    ed = int(time_range.get("end_day", 0) or 0)
    eh = int(time_range.get("end_hour", 0) or 0)
    emin = int(time_range.get("end_minute", 0) or 0)
    es = int(time_range.get("end_second", 0) or 0)

    # 使用秒展示（end_second==0 视为 ∞）
    start_seconds = sh * 3600 + smin * 60 + ss
    end_seconds = eh * 3600 + emin * 60 + es

    # 全零显示“全部时间”
    if (
        sy == 0
        and sm == 0
        and sd == 0
        and start_seconds == 0
        and ey == 0
        and em == 0
        and ed == 0
        and end_seconds == 0
    ):
        return "全部时间 (将获取全部消息)"

    start_date = fmt_date(sy, sm, sd)
    start_time = fmt_time(start_seconds)
    end_date = fmt_date(ey, em, ed)
    end_time = fmt_time(end_seconds) if end_seconds > 0 else "∞"

    start_part = f"{start_date} {start_time}" if start_date != "不限" else start_time
    end_part = (
        f"{end_date} {end_time}" if end_date != "不限" and end_time != "∞" else end_time
    )
    return f"{start_part} - {end_part}"


def parse_time_range_to_dates(
    time_range: Dict[str, int], now: Optional[datetime] = None
) -> Tuple[datetime, Optional[datetime], int, int]:
    """从时间范围配置解析出 begin_date/end_date 以及 start_s/end_s（当天秒）。
    返回: (begin_date, end_date, start_s, end_s)
    """
    now = now or datetime.now(timezone.utc)

    sy = clamp_time_component(time_range.get("start_year", 0), "year")
    sm = clamp_time_component(time_range.get("start_month", 0), "month")
    sd = clamp_time_component(time_range.get("start_day", 0), "day")
    ss = clamp_time_component(
        (time_range.get("start_hour", 0) or 0) * 3600
        + (time_range.get("start_minute", 0) or 0) * 60
        + (time_range.get("start_second", 0) or 0),
        "seconds",
    )

    ey = clamp_time_component(time_range.get("end_year", 0), "year")
    em = clamp_time_component(time_range.get("end_month", 0), "month")
    ed = clamp_time_component(time_range.get("end_day", 0), "day")
    es = clamp_time_component(
        (time_range.get("end_hour", 0) or 0) * 3600
        + (time_range.get("end_minute", 0) or 0) * 60
        + (time_range.get("end_second", 0) or 0),
        "seconds",
    )

    # begin_date 计算
    if sy == 0 and sm == 0 and sd == 0 and ss == 0:
        begin_date = datetime(2010, 1, 1, tzinfo=timezone.utc)
    else:
        try:
            if sy > 0 and sm > 0 and sd > 0:
                begin_date = datetime(sy, sm, sd, tzinfo=timezone.utc)
            elif sy > 0 and sm > 0:
                begin_date = datetime(sy, sm, 1, tzinfo=timezone.utc)
            elif sy > 0:
                begin_date = datetime(sy, 1, 1, tzinfo=timezone.utc)
            elif sd > 0:
                begin_date = now - timedelta(days=sd)
            else:
                begin_date = now - timedelta(days=30)
            if ss > 0:
                begin_date = begin_date + timedelta(seconds=ss)
        except Exception:
            begin_date = now - timedelta(days=30)

    # end_date 计算
    end_date: Optional[datetime] = None
    if ey > 0 or em > 0 or ed > 0:
        try:
            if ey > 0 and em > 0 and ed > 0:
                end_date = datetime(ey, em, ed, tzinfo=timezone.utc)
            elif ey > 0 and em > 0:
                import calendar

                last_day = calendar.monthrange(ey, em)[1]
                end_date = datetime(ey, em, last_day, 23, 59, 59, tzinfo=timezone.utc)
            elif ey > 0:
                end_date = datetime(ey, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            if es > 0 and end_date is not None:
                end_date = end_date.replace(hour=0, minute=0, second=0) + timedelta(
                    seconds=es
                )
        except Exception:
            end_date = None

    start_s = ss % (24 * 3600)
    end_s = es % (24 * 3600) if es > 0 else 0
    return begin_date, end_date, start_s, end_s
