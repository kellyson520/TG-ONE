"""
事件适配器模块

使用端口/适配器模式，将 Telegram 框架事件转换为标准化的业务事件。
"""

from __future__ import annotations
import logging
from typing import Any, Optional, Protocol
from dataclasses import dataclass

from telethon import events
from utils.helpers.chat_context import extract_chat_context

logger = logging.getLogger(__name__)


@dataclass
class MessageEvent:
    """标准化消息事件"""
    original_event: Any
    chat_id: int
    sender_id: int
    message_id: int
    message_text: Optional[str]
    grouped_id: Optional[str]
    is_media: bool
    is_media_group: bool
    chat_context: Any


class EventAdapter(Protocol):
    """事件适配器接口"""
    
    async def adapt_event(self, event: Any) -> MessageEvent:
        """将原始事件转换为标准化事件"""
        ...


class TelegramEventAdapter:
    """Telegram 事件适配器"""
    
    async def adapt_event(self, event: events.NewMessage.Event) -> MessageEvent:
        """将 Telegram 事件转换为标准化消息事件"""
        try:
            # 提取聊天上下文
            context = await extract_chat_context(event)
            
            # 构建标准化事件
            return MessageEvent(
                original_event=event,
                chat_id=context.chat_id,
                sender_id=context.sender_id,
                message_id=event.message.id,
                message_text=event.message.text,
                grouped_id=event.message.grouped_id,
                is_media=bool(event.message.media),
                is_media_group=bool(event.message.grouped_id),
                chat_context=context
            )
        except Exception as e:
            logger.error(f"事件适配失败: {str(e)}", exc_info=True)
            raise


class BotMessageFilter:
    """机器人消息过滤器"""
    
    def __init__(self, bot_id: Optional[int] = None):
        self.bot_id = bot_id
    
    def set_bot_id(self, bot_id: int) -> None:
        """设置机器人ID"""
        self.bot_id = bot_id
        logger.info(f"设置机器人ID: {bot_id}")
    
    async def should_process(self, event: events.NewMessage.Event) -> bool:
        """判断是否应该处理该事件"""
        if self.bot_id is None:
            return True
        
        try:
            sender_id = int(event.sender_id) if event.sender_id is not None else None
            is_not_bot = sender_id != self.bot_id
            
            if not is_not_bot:
                logger.debug(f"过滤机器人消息: {sender_id}")
            
            return is_not_bot
        except (ValueError, TypeError):
            return True
