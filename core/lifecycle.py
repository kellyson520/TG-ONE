"""
TG ONE 统一生命周期管理中心 (Lifecycle Manager)
负责整合应用启动 (Bootstrap) 和 优雅关闭 (Shutdown) 流程。
"""
import asyncio
import logging
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
        self.stop_event = asyncio.Event()
        self.exit_code = 0

    @classmethod
    def get_instance(cls, user_client: Optional[TelegramClient] = None, bot_client: Optional[TelegramClient] = None) -> 'LifecycleManager':
        if cls._instance is None:
            if user_client is None or bot_client is None:
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
            logger.info("LifecycleManager: System startup sequence complete.")
        except Exception as e:
            logger.critical(f"LifecycleManager: Critical error during startup: {e}")
            await self.stop()
            raise

    def shutdown(self, exit_code: int = 0) -> None:
        """触发停止信号 (同步方法，可从信号处理程序调用)"""
        logger.info(f"LifecycleManager: Shutdown signal received (code: {exit_code})")
        self.exit_code = exit_code
        self.stop_event.set()

    async def stop(self) -> None:
        """停止系统 (执行实际的清理工作)"""
        # 确保 stop_event 被设置，防止等待者死锁
        if not self.stop_event.is_set():
            self.stop_event.set()

        if self.coordinator.is_shutting_down():
            logger.debug("LifecycleManager: Shutdown already in progress, skipping.")
            return
            
        logger.info("LifecycleManager: Initiating shutdown...")
        await self.coordinator.shutdown()
        self._running = False
        logger.info("LifecycleManager: System shutdown complete.")

    @property
    def is_running(self) -> bool:
        return self._running

# 原生导出
def get_lifecycle(user_client: Optional[TelegramClient] = None, bot_client: Optional[TelegramClient] = None) -> LifecycleManager:
    return LifecycleManager.get_instance(user_client, bot_client)
