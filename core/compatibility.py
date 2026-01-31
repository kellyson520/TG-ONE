import logging
from typing import Any
from telethon.network.connection.connection import Connection

logger = logging.getLogger(__name__)

# 保存原始的 _send 方法
_original_send = Connection._send

def _patched_send(self: Connection, data: Any) -> Any:
    try:
        # 尝试调用原始发送逻辑
        return _original_send(self, data)
    except RuntimeError as e:
        # 检查是否为 uvloop 特有的 "TCPTransport closed" 错误
        if 'closed' in str(e) and 'TCPTransport' in str(e):
            logger.warning(f"[Patch] 捕获 uvloop 传输关闭错误，转换为 ConnectionResetError 以触发重连: {e}")
            # 抛出 Telethon 能识别的 ConnectionResetError (OSError 的子类)
            raise ConnectionResetError("Connection lost (uvloop compatibility fix)") from e
        # 如果是其他 Runtime 错误，原样抛出
        raise e

def apply_uvloop_patch() -> None:
    """应用 uvloop 兼容性补丁"""
    Connection._send = _patched_send  # type: ignore
    logger.info("已应用 uvloop TCPTransport 兼容性补丁")
