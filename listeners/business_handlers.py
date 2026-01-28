"""
业务处理器模块

将业务逻辑从事件监听中分离出来，提供清晰的业务处理接口。
"""

from __future__ import annotations
import logging
from typing import Any
from abc import ABC, abstractmethod

from handlers import bot_handler
from core.container import container
from core.helpers.metrics import (
    MESSAGES_RECEIVED_TOTAL,
    MESSAGE_FAILURES_TOTAL,
)
from .event_adapters import MessageEvent

logger = logging.getLogger(__name__)


class BusinessHandler(ABC):
    """业务处理器基类"""
    
    @abstractmethod
    async def handle(self, event: MessageEvent, user_client: Any, bot_client: Any) -> None:
        """处理业务事件"""
        pass


class UserMessageHandler(BusinessHandler):
    """用户消息业务处理器"""
    
    async def handle(self, event: MessageEvent, user_client: Any, bot_client: Any) -> None:
        """处理用户客户端收到的消息，只写入任务队列"""
        logger.debug("开始处理用户消息")
        MESSAGES_RECEIVED_TOTAL.labels(source='user').inc()
        
        try:
            # 极速写入，毫秒级返回
            # [Fix] 安全获取 message_id，防止 MessageEvent 结构不匹配
            msg_id = getattr(event, "message_id", None)
            if msg_id is None:
                # 尝试从 original_event 获取
                if hasattr(event, "original_event") and hasattr(event.original_event, "id"):
                    msg_id = event.original_event.id
            
            payload = {"chat_id": event.chat_id, "message_id": msg_id}
            # Use Backpressure Queue
            await container.queue_service.enqueue(
                ("process_message", payload, 0)
            )
            # await container.task_repo.push("process_message", payload)
            logger.debug(f"消息已写入任务队列: chat_id={event.chat_id}, message_id={msg_id}")
            
        except Exception as e:
            logger.error(f'处理用户消息时发生错误: {str(e)}', exc_info=True)
            MESSAGE_FAILURES_TOTAL.labels(reason='handler_exception').inc()


class BotMessageHandler(BusinessHandler):
    """机器人消息业务处理器"""
    
    async def handle(self, event: MessageEvent, user_client: Any, bot_client: Any) -> None:
        """处理机器人客户端收到的消息（命令）"""
        try:
            logger.debug("开始处理机器人消息")
            
            # [Refactor Fix] StateManager 逻辑重构
            # 由于 managers.state_manager 已移除，这里直接处理命令
            # 如果需要状态管理，通过 container.session_service 获取状态
            
            # 直接转发给 bot_handler 处理，由 bot_handler 内部解决状态问题
            await bot_handler.handle_command(bot_client, event.original_event)
            
        except Exception as e:
            logger.error(f'处理机器人命令时发生错误: {str(e)}', exc_info=True)
