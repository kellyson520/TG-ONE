import logging
import os
import re
import time
from typing import Tuple, Union

from utils.auto_delete import send_message_and_delete

logger = logging.getLogger(__name__)

# 简单的进程内去重缓存：(chat_id, code) -> last_sent_monotonic
_LAST_SENT: dict[tuple[int, str], float] = {}


def _to_text(error: Union[BaseException, str]) -> str:
    try:
        if isinstance(error, BaseException):
            text = str(error) or error.__class__.__name__
        else:
            text = str(error)
        return text
    except Exception:
        return ""


def normalize_error_reason(error: Union[BaseException, str]) -> Tuple[str, str]:
    """
    将 Telethon 常见错误映射为统一 code 与人类可读文案。

    返回: (code, human_message)
    """
    raw_text = _to_text(error)
    upper_text = raw_text.upper() if raw_text else ""

    # FLOOD_WAIT_xxx
    m = re.search(r"FLOOD_WAIT[_ ](\d+)", upper_text)
    if m:
        seconds = m.group(1)
        return "FLOOD_WAIT", f"触发平台限流，请在 {seconds} 秒后重试"

    # SLOWMODE_WAIT_xxx
    m = re.search(r"SLOWMODE_WAIT[_ ](\d+)", upper_text)
    if m:
        seconds = m.group(1)
        return "SLOWMODE_WAIT", f"目标会话慢速模式限制，请在 {seconds} 秒后再试"

    # 常见权限/对象错误
    if "CHAT_WRITE_FORBIDDEN" in upper_text:
        return "CHAT_WRITE_FORBIDDEN", "无权限在目标会话发言"
    if "PEER_ID_INVALID" in upper_text:
        return "PEER_ID_INVALID", "无效的目标会话（可能未加入或被封禁）"
    if "USER_BANNED_IN_CHANNEL" in upper_text:
        return "USER_BANNED_IN_CHANNEL", "账号在目标频道被限制"
    if "CHAT_ADMIN_REQUIRED" in upper_text:
        return "CHAT_ADMIN_REQUIRED", "需要管理员权限执行此操作"
    if "CHAT_FORBIDDEN" in upper_text or "CHANNEL_PRIVATE" in upper_text:
        return "CHAT_FORBIDDEN", "目标会话不可用或已被封禁/设置为私有"
    if "BOT_MISSING_PERMISSIONS" in upper_text:
        return "BOT_MISSING_PERMISSIONS", "机器人缺少必要权限"
    if "MSG_ID_INVALID" in upper_text:
        return "MSG_ID_INVALID", "消息 ID 无效或已过期"
    if "MEDIA_EMPTY" in upper_text:
        return "MEDIA_EMPTY", "消息内容为空或媒体不可用"
    if "MESSAGE_TOO_LONG" in upper_text or "MESSAGE_NOT_MODIFIED" in upper_text:
        if "MESSAGE_NOT_MODIFIED" in upper_text:
            return "MESSAGE_NOT_MODIFIED", "消息未发生变化，无需更新"
        return "MESSAGE_TOO_LONG", "消息过长，请精简内容或分段发送"
    if "MEDIA_CAPTION_TOO_LONG" in upper_text:
        return "MEDIA_CAPTION_TOO_LONG", "媒体描述过长，请精简"
    if "FILE_REFERENCE_EXPIRED" in upper_text:
        return "FILE_REFERENCE_EXPIRED", "文件引用已过期，请重新获取后再试"

    # 网络/平台暂时异常
    if "TIMEOUT" in upper_text or "TIMED OUT" in upper_text:
        return "TIMEOUT", "请求超时，请稍后再试"
    if (
        "INTERNAL" in upper_text
        or "RPC_CALL_FAIL" in upper_text
        or "SERVER_ERROR" in upper_text
    ):
        return "SERVER_ERROR", "平台服务暂时异常，请稍后再试"

    # 回退：使用异常类名作为 code
    if isinstance(error, BaseException):
        return error.__class__.__name__, raw_text or "发生未知错误"
    return "UNEXPECTED_ERROR", raw_text or "发生未知错误"


async def notify_error_throttled(
    client,
    chat_id: int,
    rule_id: Union[str, int, None],
    error: Union[BaseException, str],
    *,
    throttle_seconds: int | None = None,
    delete_after_seconds: int = 15,
) -> bool:
    """
    发送统一、人性化错误提示，并在同一 chat 同一错误 code 内进行节流去重。

    返回是否实际发送。
    """
    try:
        if throttle_seconds is None:
            throttle_seconds = int(os.getenv("ERROR_NOTIFY_THROTTLE_SECONDS", "30"))

        code, human = normalize_error_reason(error)
        key = (int(chat_id), str(code))

        now = time.monotonic()
        last = _LAST_SENT.get(key, 0.0)
        if now - last < max(0, throttle_seconds):
            # 在节流窗口内，跳过重复发送
            logger.debug(f"跳过重复错误提示 chat={chat_id} code={code}")
            return False

        _LAST_SENT[key] = now
        rid_text = f"规则 {rule_id}" if rule_id is not None else "规则"
        text = f"⚠️ 转发失败（{rid_text}）：{human}"
        await send_message_and_delete(
            client, chat_id, text, delete_after_seconds=delete_after_seconds
        )
        return True
    except Exception as e:
        logger.error(f"发送错误提示失败: {e}")
        return False
