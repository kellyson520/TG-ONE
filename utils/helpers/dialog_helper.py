"""
对话获取助手模块
提供带有重试机制和错误处理的对话获取功能
"""

import asyncio
import time
from telethon import errors
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import Dialog
from typing import AsyncGenerator, List, Optional

from utils.core.logger_utils import get_logger

logger = get_logger(__name__)


class DialogHelper:
    """对话获取助手类"""

    def __init__(self, client):
        self.client = client

    async def iter_dialogs_safe(
        self,
        limit: int = None,
        offset_date=None,
        offset_id: int = 0,
        offset_peer=None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 30.0,
    ) -> AsyncGenerator[Dialog, None]:
        """
        安全的对话迭代器，带有重试机制和错误处理

        Args:
            limit: 限制返回的对话数量
            offset_date: 偏移日期
            offset_id: 偏移ID
            offset_peer: 偏移对等体
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            timeout: 超时时间（秒）

        Yields:
            Dialog: 对话对象
        """
        retries = 0
        start_time = time.time()

        while retries <= max_retries:
            try:
                # 检查超时
                if time.time() - start_time > timeout:
                    logger.warning(f"对话获取超时 ({timeout}秒)")
                    break

                # 使用异步超时包装
                async with asyncio.timeout(timeout):
                    dialog_count = 0
                    async for dialog in self.client.iter_dialogs(
                        limit=limit,
                        offset_date=offset_date,
                        offset_id=offset_id,
                        offset_peer=offset_peer,
                    ):
                        yield dialog
                        dialog_count += 1

                        # 如果指定了限制且达到限制，退出
                        if limit and dialog_count >= limit:
                            break

                # 成功完成，退出重试循环
                logger.debug(f"成功获取 {dialog_count} 个对话")
                break

            except FloodWaitError as e:
                # Telegram要求等待
                wait_time = e.seconds
                logger.warning(f"遇到FloodWait错误，需要等待 {wait_time} 秒")

                if wait_time > 60:  # 如果等待时间超过1分钟，直接放弃
                    logger.error(f"FloodWait等待时间过长 ({wait_time}秒)，放弃重试")
                    break

                await asyncio.sleep(wait_time)
                retries += 1

            except RPCError as e:
                # RPC错误（包括网络和服务器错误）
                retries += 1
                if retries <= max_retries:
                    delay = base_delay * (2 ** (retries - 1))  # 指数退避
                    logger.warning(f"RPC错误 (重试 {retries}/{max_retries}): {e}")
                    logger.info(f"等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"达到最大重试次数，放弃获取对话: {e}")
                    break

            except (ConnectionError, OSError) as e:
                # 网络连接错误
                retries += 1
                if retries <= max_retries:
                    delay = base_delay * (2 ** (retries - 1))
                    logger.warning(f"网络连接错误 (重试 {retries}/{max_retries}): {e}")
                    logger.info(f"等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"达到最大重试次数，网络连接失败: {e}")
                    break

            except asyncio.TimeoutError:
                retries += 1
                if retries <= max_retries:
                    delay = base_delay * (2 ** (retries - 1))
                    logger.warning(f"请求超时 (重试 {retries}/{max_retries})")
                    logger.info(f"等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("达到最大重试次数，请求超时")
                    break

            except Exception as e:
                # 其他未预期的错误
                logger.error(f"获取对话时发生未预期错误: {e}")
                retries += 1
                if retries <= max_retries:
                    delay = base_delay * (2 ** (retries - 1))
                    logger.info(f"等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("达到最大重试次数，放弃")
                    break

    async def find_dialog_by_name(
        self,
        name: str,
        limit: int = 100,
        case_sensitive: bool = False,
        max_retries: int = 3,
    ) -> Optional[Dialog]:
        """
        根据名称查找对话

        Args:
            name: 要查找的名称
            limit: 搜索的对话数量限制
            case_sensitive: 是否区分大小写
            max_retries: 最大重试次数

        Returns:
            找到的对话对象，如果没找到返回None
        """
        try:
            search_name = name if case_sensitive else name.lower()

            async for dialog in self.iter_dialogs_safe(
                limit=limit, max_retries=max_retries
            ):
                dialog_name = getattr(dialog, "name", "") or ""
                compare_name = dialog_name if case_sensitive else dialog_name.lower()

                if search_name in compare_name:
                    logger.debug(f"找到匹配对话: {dialog_name}")
                    return dialog

            logger.debug(f"未找到名称包含 '{name}' 的对话")
            return None

        except Exception as e:
            logger.error(f"查找对话时发生错误: {e}")
            return None

    async def get_dialogs_list(
        self, limit: int = None, max_retries: int = 3
    ) -> List[Dialog]:
        """
        获取对话列表

        Args:
            limit: 限制数量
            max_retries: 最大重试次数

        Returns:
            对话列表
        """
        dialogs = []
        try:
            async for dialog in self.iter_dialogs_safe(
                limit=limit, max_retries=max_retries
            ):
                dialogs.append(dialog)

            logger.debug(f"成功获取 {len(dialogs)} 个对话")
            return dialogs

        except Exception as e:
            logger.error(f"获取对话列表时发生错误: {e}")
            return dialogs


# 便利函数
async def safe_iter_dialogs(client, **kwargs):
    """便利函数：安全的对话迭代"""
    helper = DialogHelper(client)
    async for dialog in helper.iter_dialogs_safe(**kwargs):
        yield dialog


async def safe_find_dialog_by_name(client, name: str, **kwargs) -> Optional[Dialog]:
    """便利函数：根据名称安全查找对话"""
    helper = DialogHelper(client)
    return await helper.find_dialog_by_name(name, **kwargs)


async def safe_get_dialogs_list(client, **kwargs) -> List[Dialog]:
    """便利函数：安全获取对话列表"""
    helper = DialogHelper(client)
    return await helper.get_dialogs_list(**kwargs)
