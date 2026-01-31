"""
实体有效性验证工具
在获取实体前先检查是否可能有效，减少不必要的API调用
"""

import logging
import re
from typing import Tuple, Union, Set

logger = logging.getLogger(__name__)


class EntityValidator:
    """实体有效性验证器"""

    def __init__(self) -> None:
        # 已知的无效实体ID缓存（避免重复尝试）
        self.invalid_entities: Set[str] = set()

    def is_likely_valid_user_id(self, user_id: Union[int, str]) -> bool:
        """
        检查用户ID是否可能有效

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否可能有效
        """
        try:
            # 转换为整数
            uid = int(user_id)

            # Telegram用户ID范围检查
            if uid <= 0:
                return False

            # 用户ID通常在合理范围内（1-10^10）
            if uid > 10**10:
                return False

            # 检查是否在黑名单中
            if str(uid) in self.invalid_entities:
                return False

            return True

        except (ValueError, TypeError):
            return False

    def is_likely_valid_chat_id(self, chat_id: Union[int, str]) -> bool:
        """
        检查聊天ID是否可能有效

        Args:
            chat_id: 聊天ID

        Returns:
            bool: 是否可能有效
        """
        try:
            # 处理字符串形式的ID
            if isinstance(chat_id, str):
                if chat_id.startswith("@"):
                    # 用户名格式，进行基本验证
                    return self.is_valid_username(chat_id)
                else:
                    chat_id = int(chat_id)

            # 负数ID通常是群组
            if chat_id < 0:
                # 超级群组ID范围
                if -(10**13) < chat_id < -(10**9):
                    return True
                # 普通群组ID范围
                elif -(10**9) < chat_id < 0:
                    return True
                else:
                    return False

            # 正数ID通常是用户或频道
            return self.is_likely_valid_user_id(chat_id)

        except (ValueError, TypeError):
            return False

    def is_valid_username(self, username: str) -> bool:
        """
        检查用户名格式是否有效

        Args:
            username: 用户名（如 @channel_name）

        Returns:
            bool: 格式是否有效
        """
        if not username.startswith("@"):
            return False

        # 移除@符号
        name = username[1:]

        # 用户名规则：5-32字符，只能包含字母、数字、下划线
        if not (5 <= len(name) <= 32):
            return False

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*[a-zA-Z0-9]$", name):
            return False

        return True

    def mark_invalid(self, entity_id: Union[int, str]) -> None:
        """
        标记实体为无效

        Args:
            entity_id: 实体ID
        """
        self.invalid_entities.add(str(entity_id))
        logger.debug(f"标记实体为无效: {entity_id}")

    def remove_invalid(self, entity_id: Union[int, str]) -> None:
        """
        从无效列表中移除实体

        Args:
            entity_id: 实体ID
        """
        self.invalid_entities.discard(str(entity_id))
        logger.debug(f"从无效列表移除: {entity_id}")

    def clear_invalid_cache(self) -> None:
        """清理无效实体缓存"""
        self.invalid_entities.clear()
        logger.info("无效实体缓存已清理")

    def get_invalid_count(self) -> int:
        """获取无效实体数量"""
        return len(self.invalid_entities)

    def analyze_entity_error(
        self, entity_id: Union[int, str], error: str
    ) -> Tuple[bool, str]:
        """
        分析实体获取错误，判断是否为永久性错误

        Args:
            entity_id: 实体ID
            error: 错误信息

        Returns:
            Tuple[bool, str]: (是否为永久性错误, 错误分类)
        """
        error_lower = error.lower()

        # 永久性错误（不需要重试）
        if any(
            keyword in error_lower
            for keyword in [
                "cannot find any entity",
                "no such peer",
                "user not found",
                "chat not found",
                "channel private",
                "deleted account",
            ]
        ):
            self.mark_invalid(entity_id)
            return True, "实体不存在或无法访问"

        # 临时性错误（可以重试）
        if any(
            keyword in error_lower
            for keyword in [
                "timeout",
                "network",
                "connection",
                "flood wait",
                "rate limit",
            ]
        ):
            return False, "临时网络或限频错误"

        # 权限错误（可能是临时的）
        if any(
            keyword in error_lower
            for keyword in ["forbidden", "access denied", "permission denied"]
        ):
            return False, "权限或访问错误"

        # 未知错误，保守处理
        return False, "未知错误类型"


# 全局实例
entity_validator = EntityValidator()


def get_entity_validator() -> EntityValidator:
    """获取实体验证器实例"""
    return entity_validator
