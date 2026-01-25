"""聊天上下文提取工具模块"""

from __future__ import annotations

import logging
import os
from telethon.tl import types
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ChatContext:
    """聊天上下文信息"""

    def __init__(
        self, chat_id: int, sender_id: Optional[int], is_channel: bool, raw_chat_id: int
    ):
        self.chat_id = chat_id  # 处理后的聊天ID
        self.sender_id = sender_id  # 发送者ID
        self.is_channel = is_channel  # 是否为频道消息
        self.raw_chat_id = raw_chat_id  # 原始聊天ID


async def extract_chat_context(event: Any) -> ChatContext:
    """从事件中提取统一的聊天上下文

    处理频道ID的100前缀逻辑，统一发送者ID获取

    Args:
        event: Telegram事件对象

    Returns:
        ChatContext: 聊天上下文信息
    """
    try:
        chat = await event.get_chat()
        raw_chat_id = abs(chat.id)
        chat_id = raw_chat_id
        is_channel = isinstance(event.chat, types.Channel)

        # 处理频道消息的ID格式
        if is_channel:
            logger.debug("检测到频道消息")
            # 频道ID需要加上100前缀
            chat_id = int(f"100{raw_chat_id}")

        # 获取发送者ID
        sender_id = event.sender_id
        logger.debug(
            f"消息处理: sender_id={sender_id}, chat_id={chat_id}, is_channel={is_channel}"
        )

        return ChatContext(
            chat_id=chat_id,
            sender_id=sender_id,
            is_channel=is_channel,
            raw_chat_id=raw_chat_id,
        )

    except Exception as e:
        error_msg = str(e).lower()

        # 特殊处理数据库只读错误
        if (
            "readonly database" in error_msg
            or "attempt to write a readonly database" in error_msg
        ):
            logger.critical(f"数据库只读错误: {str(e)}")
            logger.critical(
                '建议执行权限修复: python -c "from utils.database_manager import ensure_database_permissions; ensure_database_permissions()"'
            )

            # 尝试自动修复
            try:
                import asyncio

                from utils.database_manager import ensure_database_permissions

                logger.info("尝试自动修复数据库权限...")
                # 使用线程池执行同步操作，避免阻塞事件循环
                if await asyncio.to_thread(ensure_database_permissions):
                    logger.info("数据库权限修复成功，请重启应用")
                else:
                    logger.error("数据库权限修复失败，需要手动处理")
            except ImportError:
                logger.error("无法导入数据库管理器，请手动修复权限")

        logger.error(f"提取聊天上下文失败: {str(e)}", exc_info=True)

        # 返回默认上下文
        return ChatContext(chat_id=0, sender_id=None, is_channel=False, raw_chat_id=0)


def normalize_channel_id(channel_id: str) -> str:
    """标准化频道ID格式

    Args:
        channel_id: 原始频道ID字符串

    Returns:
        str: 标准化后的频道ID
    """
    channel_id_str = str(channel_id)

    # 移除-100前缀
    if channel_id_str.startswith("-100"):
        return channel_id_str[4:]
    # 移除100前缀
    elif channel_id_str.startswith("100"):
        return channel_id_str[3:]

    return channel_id_str


def add_channel_prefix(channel_id: str) -> str:
    """为频道ID添加-100前缀

    Args:
        channel_id: 频道ID字符串

    Returns:
        str: 带-100前缀的频道ID
    """
    channel_id_str = str(channel_id)

    # 如果已有前缀，直接返回
    if channel_id_str.startswith("-100"):
        return channel_id_str

    # 移除可能的其他前缀再添加
    normalized = normalize_channel_id(channel_id_str)
    return f"-100{normalized}"
