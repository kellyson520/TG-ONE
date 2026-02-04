"""Telegram UI 辅助函数"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 全局编辑锁，防止并发编辑同一消息
_edit_locks: Dict[int, asyncio.Lock] = {}
_edit_lock_cleanup_time: Dict[int, float] = {}


def _get_edit_lock(message_id: int) -> asyncio.Lock:
    """获取指定消息的编辑锁"""
    current_time = time.time()

    # 清理超过5分钟未使用的锁
    expired_keys = [
        key
        for key, last_time in _edit_lock_cleanup_time.items()
        if current_time - last_time > 300
    ]
    for key in expired_keys:
        _edit_locks.pop(key, None)
        _edit_lock_cleanup_time.pop(key, None)

    if message_id not in _edit_locks:
        _edit_locks[message_id] = asyncio.Lock()

    _edit_lock_cleanup_time[message_id] = current_time
    return _edit_locks[message_id]


async def safe_edit(
    event: Any, text: str, buttons: Optional[List] = None, max_retries: int = 3
) -> bool:
    """安全编辑消息，若内容未变化则不抛错。

    增强版本：
    - 添加并发控制锁机制
    - 增加重试机制
    - 改进错误处理

    Returns:
        bool: True 表示已成功编辑；False 表示未编辑（包括内容未变或无权限编辑等情况）。
    """
    try:
        # 获取消息ID用于锁定
        try:
            current_msg = await event.get_message()
            message_id = current_msg.id if current_msg else hash(str(event))
        except Exception:
            message_id = hash(str(event))

        # 获取编辑锁
        edit_lock = _get_edit_lock(message_id)

        async with edit_lock:
            for attempt in range(max_retries):
                try:
                    # 检查当前内容是否一致
                    try:
                        cur = await event.get_message()
                        cur_text = getattr(cur, "message", None)
                        if cur_text == text and buttons is None:
                            logger.debug("safe_edit: 内容一致，跳过编辑")
                            return False
                    except Exception as e:
                        logger.debug(f"safe_edit: 获取当前消息失败: {e}")

                    # 执行编辑
                    await event.edit(text, buttons=buttons)
                    logger.debug("safe_edit: 编辑成功")
                    return True

                except Exception as e:
                    error_msg = str(e).lower()

                    # 明确的非可恢复情形：直接忽略且不再重试
                    if "not modified" in error_msg:
                        try:
                            await event.answer("已更新")
                        except Exception as e:
                            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                        logger.debug("safe_edit: 内容未修改，忽略")
                        return False
                    if (
                        "message to edit not found" in error_msg
                        or "message id is invalid" in error_msg
                        or "can't do that operation" in error_msg
                        or "author required" in error_msg
                        or "edit time expired" in error_msg
                        or "admin required" in error_msg
                    ):
                        logger.debug(f"safe_edit: 非可恢复编辑错误，忽略: {e}")
                        return False

                    if attempt < max_retries - 1:
                        # 重试前等待短暂时间（针对网络类可恢复错误）
                        await asyncio.sleep(0.1 * (attempt + 1))
                        logger.debug(f"safe_edit: 重试 {attempt + 1}/{max_retries}")
                        continue
                    else:
                        # 最后一次尝试失败也不再上报 error，降噪
                        logger.debug(f"safe_edit: 所有重试失败，放弃: {e}")
                        return False

    except Exception as e:
        # 顶层兜底降级为调试日志，避免重复打扰
        logger.debug(f"safe_edit: 编辑异常（已忽略）: {e}")
        return False


async def safe_edit_message(
    client: Any,
    chat_id: int,
    message_id: int,
    text: str,
    buttons: Optional[List] = None,
    max_retries: int = 3,
) -> None:
    """安全地通过 client.edit_message 编辑指定消息，内容未变化时不调用编辑。

    增强版本：
    - 添加并发控制锁机制
    - 增加重试机制
    - 改进错误处理
    """
    # 获取编辑锁
    edit_lock = _get_edit_lock(message_id)

    async with edit_lock:
        for attempt in range(max_retries):
            try:
                # 检查当前内容是否一致
                try:
                    cur = await client.get_messages(chat_id, ids=message_id)
                    cur_text = getattr(cur, "message", None) if cur else None
                    if cur_text == text and buttons is None:
                        logger.debug("safe_edit_message: 内容一致，跳过编辑")
                        return
                except Exception as e:
                    logger.debug(f"safe_edit_message: 获取当前消息失败: {e}")

                # 执行编辑
                await client.edit_message(chat_id, message_id, text, buttons=buttons)
                logger.debug("safe_edit_message: 编辑成功")
                return

            except Exception as e:
                error_msg = str(e).lower()

                # 明确的非可恢复情形：直接忽略且不再重试
                if "not modified" in error_msg:
                    logger.debug("safe_edit_message: 内容未修改，忽略")
                    return
                if (
                    "message to edit not found" in error_msg
                    or "message id is invalid" in error_msg
                    or "can't do that operation" in error_msg
                    or "author required" in error_msg
                    or "edit time expired" in error_msg
                    or "admin required" in error_msg
                ):
                    logger.debug(f"safe_edit_message: 非可恢复编辑错误，忽略: {e}")
                    return

                if attempt < max_retries - 1:
                    # 重试前等待短暂时间（针对网络类可恢复错误）
                    await asyncio.sleep(0.1 * (attempt + 1))
                    logger.debug(f"safe_edit_message: 重试 {attempt + 1}/{max_retries}")
                    continue
                else:
                    # 最后一次尝试失败也不再上报 error，降噪
                    logger.debug(f"safe_edit_message: 所有重试失败，放弃: {e}")
                    return
