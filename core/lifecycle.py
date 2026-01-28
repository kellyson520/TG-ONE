"""
TG ONE 统一生命周期管理中心 (Lifecycle Manager)
负责整合应用启动 (Bootstrap) 和 优雅关闭 (Shutdown) 流程。
"""
import logging
from typing import Optional
from telethon import TelegramClient

from core.bootstrap import Bootstrap
from core.shutdown import get_shutdown_coordinator

logger = logging.getLogger(__name__)

class LifecycleManager:
    """系统生命周期管理器"""
    
    _instance: Optional['LifecycleManager'] = None
    
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient):
        self.bootstrap = Bootstrap(user_client, bot_client)
        self.coordinator = get_shutdown_coordinator()
        self._running = False

    @classmethod
    def get_instance(cls, user_client=None, bot_client=None) -> 'LifecycleManager':
        if cls._instance is None:
            if user_client is None or bot_client is None:
                raise ValueError("LifecycleManager not initialized. Pass clients first.")
            cls._instance = LifecycleManager(user_client, bot_client)
        return cls._instance

    async def start(self):
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

    async def stop(self):
        """停止系统"""
        logger.info("LifecycleManager: Initiating shutdown...")
        await self.coordinator.shutdown()
        self._running = False
        logger.info("LifecycleManager: System shutdown complete.")

    @property
    def is_running(self) -> bool:
        return self._running

# 原生导出
def get_lifecycle(user_client=None, bot_client=None) -> LifecycleManager:
    return LifecycleManager.get_instance(user_client, bot_client)
