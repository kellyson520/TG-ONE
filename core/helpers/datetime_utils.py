"""
日期时间工具函数
提供安全的日期时间处理和格式化功能
"""

from datetime import datetime

import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


def safe_isoformat(dt_value: Union[datetime, str, None]) -> Optional[str]:
    """
    安全地将日期时间转换为 ISO 格式字符串

    Args:
        dt_value: datetime 对象、ISO 字符串或 None

    Returns:
        ISO 格式字符串或 None
    """
    if dt_value is None:
        return None

    if isinstance(dt_value, str):
        # 如果已经是字符串，假设是 ISO 格式，直接返回
        return dt_value

    if isinstance(dt_value, datetime):
        return dt_value.isoformat()

    # 其他类型，尝试转换为字符串
    try:
        return str(dt_value)
    except Exception as e:
        logger.warning(f"无法将 {type(dt_value)} 转换为字符串: {e}")
        return None


def safe_fromisoformat(iso_string: Union[str, datetime, None]) -> Optional[datetime]:
    """
    安全地从 ISO 格式字符串解析日期时间

    Args:
        iso_string: ISO 格式字符串、datetime 对象或 None

    Returns:
        datetime 对象或 None
    """
    if iso_string is None:
        return None

    if isinstance(iso_string, datetime):
        # 如果已经是 datetime 对象，直接返回
        return iso_string

    if isinstance(iso_string, str):
        try:
            return datetime.fromisoformat(iso_string)
        except ValueError as e:
            logger.warning(f"无法解析 ISO 日期字符串 '{iso_string}': {e}")
            return None

    # 其他类型
    logger.warning(f"不支持的日期类型: {type(iso_string)}")
    return None


def get_current_isoformat() -> str:
    """
    获取当前时间的 ISO 格式字符串

    Returns:
        当前时间的 ISO 格式字符串
    """
    return datetime.utcnow().isoformat()


def format_datetime_for_display(
    dt_value: Union[datetime, str, None], format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    格式化日期时间用于显示

    Args:
        dt_value: datetime 对象、ISO 字符串或 None
        format_str: 格式化字符串

    Returns:
        格式化后的日期时间字符串
    """
    if dt_value is None:
        return "未知"

    # 先转换为 datetime 对象
    dt_obj = safe_fromisoformat(dt_value)
    if dt_obj is None:
        return "无效日期"

    try:
        return dt_obj.strftime(format_str)
    except Exception as e:
        logger.warning(f"日期格式化失败: {e}")
        return str(dt_value)


def is_valid_datetime_string(dt_string: str) -> bool:
    """
    检查字符串是否为有效的日期时间格式

    Args:
        dt_string: 日期时间字符串

    Returns:
        是否有效
    """
    if not isinstance(dt_string, str):
        return False

    try:
        datetime.fromisoformat(dt_string)
        return True
    except ValueError:
        return False


def safe_datetime_operation(
    dt_value: Union[datetime, str, None], operation: callable
) -> Optional[str]:
    """
    安全地对日期时间执行操作并返回 ISO 格式字符串

    Args:
        dt_value: 日期时间值
        operation: 要执行的操作函数（接受 datetime 对象）

    Returns:
        操作结果的 ISO 格式字符串或 None
    """
    dt_obj = safe_fromisoformat(dt_value)
    if dt_obj is None:
        return None

    try:
        result = operation(dt_obj)
        if isinstance(result, datetime):
            return result.isoformat()
        return str(result)
    except Exception as e:
        logger.warning(f"日期时间操作失败: {e}")
        return None


# 常用的日期时间操作示例
def add_days(dt_value: Union[datetime, str, None], days: int) -> Optional[str]:
    """添加天数"""
    from datetime import timedelta

    return safe_datetime_operation(dt_value, lambda dt: dt + timedelta(days=days))


def subtract_days(dt_value: Union[datetime, str, None], days: int) -> Optional[str]:
    """减去天数"""
    from datetime import timedelta

    return safe_datetime_operation(dt_value, lambda dt: dt - timedelta(days=days))


def get_age_in_days(dt_value: Union[datetime, str, None]) -> Optional[int]:
    """获取距今天数"""
    dt_obj = safe_fromisoformat(dt_value)
    if dt_obj is None:
        return None

    try:
        delta = datetime.utcnow() - dt_obj
        return delta.days
    except Exception as e:
        logger.warning(f"计算天数差异失败: {e}")
        return None
