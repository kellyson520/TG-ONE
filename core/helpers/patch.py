import platform

import asyncio
import logging
from telethon.network.connection.connection import Connection

logger = logging.getLogger(__name__)


def apply_uvloop_patch():
    """
    应用 uvloop TCPTransport 兼容性补丁，修复 RuntimeError: unable to perform operation on <TCPTransport closed=True...>
    """
    # 保存原始的 _send 方法
    _original_send = Connection._send

    def _patched_send(self, data):
        try:
            # 尝试调用原始发送逻辑
            return _original_send(self, data)
        except RuntimeError as e:
            # 检查是否为 uvloop 特有的 "TCPTransport closed" 错误
            if "closed" in str(e) and "TCPTransport" in str(e):
                logger.warning(
                    f"[Patch] 捕获 uvloop 传输关闭错误，转换为 ConnectionResetError 以触发重连: {e}"
                )
                # 抛出 Telethon 能识别的 ConnectionResetError (OSError 的子类)
                raise ConnectionResetError(
                    "Connection lost (uvloop compatibility fix)"
                ) from e
            # 如果是其他 Runtime 错误，原样抛出
            raise e

    # 应用补丁：替换 Connection 类的 _send 方法
    Connection._send = _patched_send
    logger.info("已应用 uvloop TCPTransport 兼容性补丁")


def setup_event_loop():
    """
    设置事件循环，优先使用 uvloop 以提高性能
    """
    # 尝试启用 uvloop 以提高性能
    if platform.system() != "Windows":
        try:
            import uvloop

            # 使用更安全的方式启用 uvloop，只在异步上下文中生效
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("已设置 uvloop 高性能事件循环策略")
        except ImportError:
            logger.info("未安装 uvloop，使用默认事件循环")
    else:
        logger.info("Windows 系统不支持 uvloop，使用默认事件循环")
