"""
TG ONE 统一生命周期管理中心 (Lifecycle Manager)
负责整合应用启动 (Bootstrap) 和 优雅关闭 (Shutdown) 流程。
"""
import logging
import asyncio
from typing import Optional
from telethon import TelegramClient

from core.bootstrap import Bootstrap
from core.shutdown import get_shutdown_coordinator

logger = logging.getLogger(__name__)

class LifecycleManager:
    """系统生命周期管理器"""
    
    _instance: Optional['LifecycleManager'] = None
    
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient) -> None:
        self.bootstrap = Bootstrap(user_client, bot_client)
        self.coordinator = get_shutdown_coordinator()
        self._running = False
        self._stop_event = asyncio.Event()
        self._exit_code = 0

    @classmethod
    def get_instance(cls, user_client: Optional[TelegramClient] = None, bot_client: Optional[TelegramClient] = None) -> 'LifecycleManager':
        if cls._instance is None:
            if user_client is None or bot_client is None:
                # 尝试从全局容器获取，如果还未初始化则报错
                from core.container import container
                if hasattr(container, 'lifecycle') and container.lifecycle:
                    return container.lifecycle
                raise ValueError("LifecycleManager not initialized. Pass clients first.")
            cls._instance = LifecycleManager(user_client, bot_client)
        return cls._instance

    async def start(self) -> None:
        """启动系统"""
        if self._running:
            logger.warning("LifecycleManager: System is already running.")
            return
            
        logger.info("LifecycleManager: Initiating startup...")
        try:
            await self.bootstrap.run()
            self._running = True
            self._stop_event.clear()
            logger.info("LifecycleManager: System startup sequence complete.")
        except Exception as e:
            logger.critical(f"LifecycleManager: Critical error during startup: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """停止系统"""
        if self.coordinator.is_shutting_down():
            logger.debug("LifecycleManager: Shutdown already in progress, skipping.")
            return
            
        logger.info("LifecycleManager: Initiating shutdown...")
        await self.coordinator.shutdown()
        self._running = False
        logger.info("LifecycleManager: System shutdown complete.")

    def shutdown(self, exit_code: int = 0) -> None:
        """请求系统关闭并设置退出码"""
        self._exit_code = exit_code
        self._stop_event.set()
        logger.info(f"LifecycleManager: Shutdown requested with exit code {exit_code}")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop_event

    @property
    def exit_code(self) -> int:
        return self._exit_code

# 原生导出
def get_lifecycle(user_client: Optional[TelegramClient] = None, bot_client: Optional[TelegramClient] = None) -> LifecycleManager:
    return LifecycleManager.get_instance(user_client, bot_client)
