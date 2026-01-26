"""转发规则工具函数"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_rule_info(rule: Any) -> Dict[str, Any]:
    """安全地从 ForwardRule 对象提取信息

    避免访问可能导致 DetachedInstanceError 的属性

    Args:
        rule: ForwardRule 对象

    Returns:
        Dict: 包含规则信息的字典
    """
    info = {
        "id": None,
        "enable_rule": False,
        "use_bot": False,
        "source_chat_name": "未知",
        "target_chat_name": "未知",
        "source_chat_id": None,
        "target_chat_id": None,
    }

    try:
        # 基本属性（直接存储在对象中，不涉及关联）
        info["id"] = getattr(rule, "id", None)
        info["enable_rule"] = getattr(rule, "enable_rule", False)
        info["use_bot"] = getattr(rule, "use_bot", False)
        info["source_chat_id"] = getattr(rule, "source_chat_id", None)
        info["target_chat_id"] = getattr(rule, "target_chat_id", None)

        # 关联对象（可能触发懒加载）
        try:
            if hasattr(rule, "source_chat") and rule.source_chat:
                info["source_chat_name"] = rule.source_chat.name
        except Exception as e:
            logger.debug(f"无法获取规则 {info['id']} 的源聊天名称: {str(e)}")

        try:
            if hasattr(rule, "target_chat") and rule.target_chat:
                info["target_chat_name"] = rule.target_chat.name
        except Exception as e:
            logger.debug(f"无法获取规则 {info['id']} 的目标聊天名称: {str(e)}")

    except Exception as e:
        logger.error(f"提取规则信息时出错: {str(e)}", exc_info=True)

    return info


def is_rule_enabled(rule: Any) -> bool:
    """安全地检查规则是否启用

    Args:
        rule: ForwardRule 对象

    Returns:
        bool: 规则是否启用
    """
    try:
        return bool(getattr(rule, "enable_rule", False))
    except Exception as e:
        logger.debug(f"检查规则启用状态时出错: {str(e)}")
        return False


def should_use_bot(rule: Any) -> bool:
    """安全地检查是否使用机器人客户端

    Args:
        rule: ForwardRule 对象

    Returns:
        bool: 是否使用机器人客户端
    """
    try:
        return bool(getattr(rule, "use_bot", False))
    except Exception as e:
        logger.debug(f"检查机器人使用状态时出错: {str(e)}")
        return False


def get_rule_id(rule: Any) -> Optional[int]:
    """安全地获取规则ID

    Args:
        rule: ForwardRule 对象

    Returns:
        Optional[int]: 规则ID
    """
    try:
        return getattr(rule, "id", None)
    except Exception as e:
        logger.debug(f"获取规则ID时出错: {str(e)}")
        return None
