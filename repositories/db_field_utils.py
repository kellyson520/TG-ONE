"""
数据库字段工具函数
提供安全的数据库字段操作，特别是日期时间字段的处理
"""

from datetime import datetime

import logging
from typing import Any, Optional, Union

from core.helpers.datetime_utils import safe_fromisoformat, safe_isoformat

logger = logging.getLogger(__name__)


def safe_get_datetime_field(obj: Any, field_name: str) -> Optional[str]:
    """
    安全获取对象的日期时间字段值

    Args:
        obj: 数据库对象
        field_name: 字段名

    Returns:
        ISO 格式的日期时间字符串或 None
    """
    if not hasattr(obj, field_name):
        return None

    field_value = getattr(obj, field_name)
    return safe_isoformat(field_value)


def safe_set_datetime_field(
    obj: Any, field_name: str, value: Union[datetime, str, None]
) -> bool:
    """
    安全设置对象的日期时间字段值

    Args:
        obj: 数据库对象
        field_name: 字段名
        value: 要设置的值

    Returns:
        是否设置成功
    """
    try:
        if value is None:
            setattr(obj, field_name, None)
            return True

        # 确保存储为 ISO 格式字符串
        iso_value = safe_isoformat(value)
        setattr(obj, field_name, iso_value)
        return True
    except Exception as e:
        logger.error(f"设置日期时间字段 {field_name} 失败: {e}")
        return False


def update_timestamp_fields(obj: Any, update_created: bool = False) -> None:
    """
    更新对象的时间戳字段

    Args:
        obj: 数据库对象
        update_created: 是否更新 created_at 字段
    """
    current_time = datetime.utcnow().isoformat()

    if update_created and hasattr(obj, "created_at"):
        obj.created_at = current_time

    if hasattr(obj, "updated_at"):
        obj.updated_at = current_time


def serialize_model_for_api(obj: Any, exclude_fields: Optional[list] = None) -> dict:
    """
    将数据库模型安全序列化为 API 响应格式

    Args:
        obj: 数据库对象
        exclude_fields: 要排除的字段列表

    Returns:
        序列化后的字典
    """
    if obj is None:
        return {}

    exclude_fields = exclude_fields or []
    result = {}

    for column in obj.__table__.columns:
        field_name = column.name
        if field_name in exclude_fields:
            continue

        try:
            value = getattr(obj, field_name)

            # 特殊处理日期时间字段
            if field_name.endswith("_at") and value is not None:
                # 确保日期时间字段以正确格式返回
                result[field_name] = safe_isoformat(value)
            else:
                result[field_name] = value

        except Exception as e:
            logger.warning(f"序列化字段 {field_name} 失败: {e}")
            result[field_name] = None

    return result


def validate_datetime_fields(obj: Any) -> list:
    """
    验证对象的日期时间字段格式

    Args:
        obj: 数据库对象

    Returns:
        无效字段的列表
    """
    invalid_fields = []

    for column in obj.__table__.columns:
        field_name = column.name
        if field_name.endswith("_at"):
            try:
                value = getattr(obj, field_name)
                if value is not None and isinstance(value, str):
                    # 尝试解析日期时间字符串
                    safe_fromisoformat(value)
            except Exception as e:
                logger.warning(f"字段 {field_name} 日期时间格式无效: {e}")
                invalid_fields.append(field_name)

    return invalid_fields


def fix_datetime_fields(obj: Any) -> int:
    """
    修复对象的无效日期时间字段

    Args:
        obj: 数据库对象

    Returns:
        修复的字段数量
    """
    fixed_count = 0
    current_time = datetime.utcnow().isoformat()

    for column in obj.__table__.columns:
        field_name = column.name
        if field_name.endswith("_at"):
            try:
                value = getattr(obj, field_name)
                if value is not None:
                    if isinstance(value, str):
                        # 尝试解析，如果失败则重置
                        if not safe_fromisoformat(value):
                            setattr(obj, field_name, current_time)
                            fixed_count += 1
                    elif isinstance(value, datetime):
                        # 转换为字符串格式
                        setattr(obj, field_name, value.isoformat())
                        fixed_count += 1
                    else:
                        # 其他类型，重置为当前时间
                        setattr(obj, field_name, current_time)
                        fixed_count += 1
            except Exception as e:
                logger.error(f"修复字段 {field_name} 失败: {e}")

    return fixed_count


class SafeModelSerializer:
    """
    安全的模型序列化器
    """

    @staticmethod
    def to_dict(obj: Any, include_relations: bool = False) -> dict:
        """
        将模型对象转换为字典

        Args:
            obj: 数据库对象
            include_relations: 是否包含关联对象

        Returns:
            字典表示
        """
        if obj is None:
            return {}

        result = {}

        # 基本字段
        for column in obj.__table__.columns:
            field_name = column.name
            try:
                value = getattr(obj, field_name)

                # 安全处理日期时间字段
                if field_name.endswith("_at") and value is not None:
                    result[field_name] = safe_isoformat(value)
                else:
                    result[field_name] = value

            except Exception as e:
                logger.warning(f"序列化字段 {field_name} 失败: {e}")
                result[field_name] = None

        # 关联字段（如果需要）
        if include_relations:
            try:
                for relationship in obj.__class__.__mapper__.relationships:
                    rel_name = relationship.key
                    rel_value = getattr(obj, rel_name, None)

                    if rel_value is not None:
                        if hasattr(rel_value, "__iter__") and not isinstance(
                            rel_value, str
                        ):
                            # 一对多关系
                            result[rel_name] = [
                                SafeModelSerializer.to_dict(item) for item in rel_value
                            ]
                        else:
                            # 一对一关系
                            result[rel_name] = SafeModelSerializer.to_dict(rel_value)
                    else:
                        result[rel_name] = None

            except Exception as e:
                logger.warning(f"序列化关联字段失败: {e}")

        return result

    @staticmethod
    def safe_update(
        obj: Any, data: dict, allowed_fields: Optional[list] = None
    ) -> bool:
        """
        安全更新模型对象

        Args:
            obj: 数据库对象
            data: 要更新的数据
            allowed_fields: 允许更新的字段列表

        Returns:
            是否更新成功
        """
        try:
            for field_name, value in data.items():
                if allowed_fields and field_name not in allowed_fields:
                    continue

                if hasattr(obj, field_name):
                    # 特殊处理日期时间字段
                    if field_name.endswith("_at"):
                        safe_set_datetime_field(obj, field_name, value)
                    else:
                        setattr(obj, field_name, value)

            # 自动更新 updated_at
            if hasattr(obj, "updated_at"):
                obj.updated_at = datetime.utcnow().isoformat()

            return True
        except Exception as e:
            logger.error(f"安全更新模型失败: {e}")
            return False
