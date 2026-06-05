"""
统一的消息处理工具类
用于减少重复的消息发送、编辑、错误处理代码
"""

import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import FloodWaitError, MessageNotModifiedError
from telethon.tl.custom import Button
from typing import Any, Dict, List, Optional, Union, cast

from core.helpers.error_handler import handle_errors, handle_telegram_errors

logger = logging.getLogger(__name__)


class MessageHandler:
    """统一的消息处理工具类"""

    def __init__(self, client: TelegramClient):
        """
        初始化消息处理器

        Args:
            client: Telegram客户端
        """
        self.client = client

    @handle_telegram_errors(default_return=None, max_retries=3)
    async def safe_send(
        self, chat_id: Union[int, str], text: str, **kwargs: Any
    ) -> Optional[Any]:
        """
        安全发送消息，自动处理错误和重试

        Args:
            chat_id: 聊天ID
            text: 消息文本
            **kwargs: 其他发送参数

        Returns:
            发送的消息对象或None
        """
        return await self.client.send_message(chat_id, text, **kwargs)

    @handle_telegram_errors(default_return=False, max_retries=2)
    async def safe_edit(self, message: Any, text: str, **kwargs: Any) -> bool:
        """
        安全编辑消息，自动处理错误

        Args:
            message: 要编辑的消息对象
            text: 新的消息文本
            **kwargs: 其他编辑参数

        Returns:
            bool: 是否编辑成功
        """
        try:
            await message.edit(text, **kwargs)
            return True
        except MessageNotModifiedError:
            # 消息内容未变化，视为成功
            logger.debug("消息内容未变化，跳过编辑")
            return True
        except Exception:
            raise

    @handle_telegram_errors(default_return=False, max_retries=2)
    async def safe_delete(self, message: Any) -> bool:
        """
        安全删除消息

        Args:
            message: 要删除的消息对象

        Returns:
            bool: 是否删除成功
        """
        await message.delete()
        return True

    @handle_errors(default_return=None)
    async def safe_reply(self, event: Any, text: str, **kwargs: Any) -> Optional[Any]:
        """
        安全回复消息

        Args:
            event: 消息事件
            text: 回复文本
            **kwargs: 其他回复参数

        Returns:
            回复的消息对象或None
        """
        return await event.reply(text, **kwargs)

    @handle_errors(default_return=None)
    async def safe_respond(self, event: Any, text: str, **kwargs: Any) -> Optional[Any]:
        """
        安全响应消息

        Args:
            event: 消息事件
            text: 响应文本
            **kwargs: 其他响应参数

        Returns:
            响应的消息对象或None
        """
        return await event.respond(text, **kwargs)

    async def send_with_retry(
        self, chat_id: Union[int, str], text: str, max_retries: int = 3, **kwargs: Any
    ) -> Optional[Any]:
        """
        带重试机制的消息发送
        专门处理FloodWaitError等Telegram特有错误

        Args:
            chat_id: 聊天ID
            text: 消息文本
            max_retries: 最大重试次数
            **kwargs: 其他发送参数

        Returns:
            发送的消息对象或None
        """
        for attempt in range(max_retries):
            try:
                return await self.client.send_message(chat_id, text, **kwargs)
            except FloodWaitError as e:
                if attempt < max_retries - 1:
                    wait_time = min(e.seconds, 300)  # 最多等待5分钟
                    logger.warning(
                        f"触发频率限制，等待 {wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"达到最大重试次数，频率限制未解除")
                    return None
            except Exception as e:
                logger.error(
                    f"发送消息失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # 短暂等待后重试
                    continue
                else:
                    return None

        return None

    @handle_errors(default_return=None)
    async def send_media_group(
        self,
        chat_id: Union[int, str],
        media_files: List[Any],
        caption: str = "",
        **kwargs: Any,
    ) -> Optional[List[Any]]:
        """
        发送媒体组

        Args:
            chat_id: 聊天ID
            media_files: 媒体文件列表
            caption: 说明文字
            **kwargs: 其他发送参数

        Returns:
            发送的消息列表或None
        """
        if not media_files:
            return None

        # 如果只有一个文件，使用单文件发送
        if len(media_files) == 1:
            return [
                await self.safe_send(chat_id, caption, file=media_files[0], **kwargs)
            ]

        # 多个文件使用媒体组发送
        return cast(Optional[List[Any]], await self.client.send_file(
            chat_id, media_files, caption=caption, **kwargs
        ))

    @handle_errors(default_return=None)
    async def forward_message(
        self, from_chat: Union[int, str], to_chat: Union[int, str], message_id: int
    ) -> Optional[Any]:
        """
        转发单条消息

        Args:
            from_chat: 源聊天ID
            to_chat: 目标聊天ID
            message_id: 消息ID

        Returns:
            转发的消息对象或None
        """
        return await self.client.forward_messages(to_chat, message_id, from_chat)

    @handle_errors(default_return=[])
    async def forward_messages(
        self,
        from_chat: Union[int, str],
        to_chat: Union[int, str],
        message_ids: List[int],
    ) -> List[Any]:
        """
        批量转发消息

        Args:
            from_chat: 源聊天ID
            to_chat: 目标聊天ID
            message_ids: 消息ID列表

        Returns:
            转发的消息列表
        """
        if not message_ids:
            return []

        return cast(List[Any], await self.client.forward_messages(to_chat, message_ids, from_chat))

    async def schedule_delete(self, message: Any, delay_seconds: float) -> None:
        """
        安排消息在指定时间后删除

        Args:
            message: 要删除的消息对象
            delay_seconds: 延迟秒数
        """

        async def delete_after_delay() -> None:
            await asyncio.sleep(delay_seconds)
            await self.safe_delete(message)

        # 异步执行删除任务
        asyncio.create_task(delete_after_delay())

    @handle_errors(default_return=None)
    async def edit_or_send(
        self,
        chat_id: Union[int, str],
        text: str,
        message_to_edit: Optional[Any] = None,
        **kwargs: Any,
    ) -> Optional[Any]:
        """
        编辑消息或发送新消息
        如果提供了要编辑的消息，则尝试编辑；否则发送新消息

        Args:
            chat_id: 聊天ID
            text: 消息文本
            message_to_edit: 要编辑的消息对象（可选）
            **kwargs: 其他参数

        Returns:
            消息对象或None
        """
        if message_to_edit:
            success = await self.safe_edit(message_to_edit, text, **kwargs)
            if success:
                return message_to_edit
            else:
                # 编辑失败，发送新消息
                logger.warning("消息编辑失败，发送新消息")
                return await self.safe_send(chat_id, text, **kwargs)
        else:
            return await self.safe_send(chat_id, text, **kwargs)

    @handle_errors(default_return=None)
    async def send_button_message(
        self, chat_id: Union[int, str], text: str, buttons: List[List[Button]], **kwargs: Any
    ) -> Optional[Any]:
        """
        发送带按钮的消息

        Args:
            chat_id: 聊天ID
            text: 消息文本
            buttons: 按钮列表
            **kwargs: 其他发送参数

        Returns:
            发送的消息对象或None
        """
        return await self.safe_send(chat_id, text, buttons=buttons, **kwargs)

    @handle_errors(default_return=None)
    async def answer_callback(
        self, event: Any, text: str = "", alert: bool = False
    ) -> bool:
        """
        安全回应回调查询

        Args:
            event: 回调事件
            text: 回应文本
            alert: 是否显示为警告

        Returns:
            bool: 是否回应成功
        """
        await event.answer(text, alert=alert)
        return True


class BulkMessageHandler:
    """批量消息处理器"""

    def __init__(
        self,
        client: TelegramClient,
        batch_size: int = 50,
        delay_between_batches: float = 1.0,
    ):
        """
        初始化批量消息处理器

        Args:
            client: Telegram客户端
            batch_size: 批次大小
            delay_between_batches: 批次间延迟时间
        """
        self.client = client
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
        self.message_handler = MessageHandler(client)

    async def send_bulk_messages(
        self, chat_id: Union[int, str], messages: List[str], **kwargs: Any
    ) -> List[Optional[Any]]:
        """
        批量发送消息

        Args:
            chat_id: 聊天ID
            messages: 消息文本列表
            **kwargs: 其他发送参数

        Returns:
            发送的消息对象列表
        """
        results = []

        for i in range(0, len(messages), self.batch_size):
            batch = messages[i : i + self.batch_size]
            batch_results = []

            for message_text in batch:
                result = await self.message_handler.safe_send(
                    chat_id, message_text, **kwargs
                )
                batch_results.append(result)

            results.extend(batch_results)

            # 批次间延迟
            if i + self.batch_size < len(messages):
                await asyncio.sleep(self.delay_between_batches)

        return results

    async def forward_bulk_messages(
        self,
        from_chat: Union[int, str],
        to_chat: Union[int, str],
        message_ids: List[int],
    ) -> List[Any]:
        """
        批量转发消息

        Args:
            from_chat: 源聊天ID
            to_chat: 目标聊天ID
            message_ids: 消息ID列表

        Returns:
            转发的消息列表
        """
        results = []

        for i in range(0, len(message_ids), self.batch_size):
            batch_ids = message_ids[i : i + self.batch_size]
            batch_results = await self.message_handler.forward_messages(
                from_chat, to_chat, batch_ids
            )
            results.extend(batch_results)

            # 批次间延迟
            if i + self.batch_size < len(message_ids):
                await asyncio.sleep(self.delay_between_batches)

        return results


# 全局消息处理器实例
_message_handlers: Dict[str, MessageHandler] = {}
_bulk_handlers: Dict[str, BulkMessageHandler] = {}


def get_message_handler(client: TelegramClient) -> MessageHandler:
    """
    获取消息处理器实例

    Args:
        client: Telegram客户端

    Returns:
        MessageHandler实例
    """
    client_id = str(id(client))
    if client_id not in _message_handlers:
        _message_handlers[client_id] = MessageHandler(client)
    return _message_handlers[client_id]


def get_bulk_message_handler(
    client: TelegramClient, batch_size: int = 50, delay: float = 1.0
) -> BulkMessageHandler:
    """
    获取批量消息处理器实例

    Args:
        client: Telegram客户端
        batch_size: 批次大小
        delay: 批次间延迟

    Returns:
        BulkMessageHandler实例
    """
    client_id = f"{id(client)}_{batch_size}_{delay}"
    if client_id not in _bulk_handlers:
        _bulk_handlers[client_id] = BulkMessageHandler(client, batch_size, delay)
    return _bulk_handlers[client_id]


# 便捷函数
async def safe_send_message(
    client: TelegramClient, chat_id: Union[int, str], text: str, **kwargs: Any
) -> Optional[Any]:
    """便捷的安全发送消息函数"""
    handler = get_message_handler(client)
    return await handler.safe_send(chat_id, text, **kwargs)


async def safe_edit_message(message: Any, text: str, **kwargs: Any) -> bool:
    """便捷的安全编辑消息函数"""
    # 从消息对象获取客户端（如果可能）
    if hasattr(message, "_client"):
        handler = get_message_handler(message._client)
        return await handler.safe_edit(message, text, **kwargs)
    else:
        # 降级处理
        try:
            await message.edit(text, **kwargs)
            return True
        except Exception as e:
            logger.error(f"编辑消息失败: {str(e)}")
            return False


async def safe_delete_message(message: Any) -> bool:
    """便捷的安全删除消息函数"""
    if hasattr(message, "_client"):
        handler = get_message_handler(message._client)
        return await handler.safe_delete(message)
    else:
        # 降级处理
        try:
            await message.delete()
            return True
        except Exception as e:
            logger.error(f"删除消息失败: {str(e)}")
            return False
