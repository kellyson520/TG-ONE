from core.config import settings
import logging
import asyncio
from core.event_bus import EventBus
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class NotificationService:
    """管理系统通知服务，主要用于向管理员发送消息"""
    
    def __init__(self, bot_client: TelegramClient, event_bus: EventBus):
        self.bot_client = bot_client
        self.bus = event_bus
        self.admin_ids = []
        self._load_admin_ids()
        
        # 订阅关键事件
        self.bus.subscribe("ERROR_SYSTEM", self._on_system_error)
        self.bus.subscribe("SYSTEM_ALERT", self._on_system_alert)
        self.bus.subscribe("AUTH_LOGIN_FAILED", self._on_security_alert)
        
    def _load_admin_ids(self):
        """解析并加载管理员 ID 列表"""
        raw_ids = settings.ADMIN_IDS
        self.admin_ids = []
        if raw_ids:
            for uid in raw_ids:
                try:
                    self.admin_ids.append(int(uid))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid Admin ID in settings: {uid}")
        
        logger.info(f"通知服务已初始化，当前有 {len(self.admin_ids)} 位管理员")

    async def notify_admins(self, message: str, level: str = "INFO"):
        """向所有管理员发送通知"""
        if not self.admin_ids:
            return
            
        icon = "ℹ️"
        if level == "ERROR":
            icon = "🚨"
        elif level == "WARNING":
            icon = "⚠️"
        elif level == "SUCCESS":
            icon = "✅"
            
        formatted_msg = f"{icon} **System Notification** [{level}]\n\n{message}"
        
        tasks = []
        for admin_id in self.admin_ids:
            tasks.append(self._send_safe(admin_id, formatted_msg))
            
        if tasks:
            await asyncio.gather(*tasks)

    async def _send_safe(self, user_id: int, message: str):
        """安全发送消息，忽略错误"""
        try:
            await self.bot_client.send_message(user_id, message)
        except Exception as e:
            logger.warning(f"Failed to send notification to admin {user_id}: {e}")

    async def _on_system_error(self, data: dict):
        """处理系统错误事件"""
        msg = f"Module: `{data.get('module', 'Unknown')}`\nError: `{data.get('error', 'Unknown')}`"
        await self.notify_admins(msg, level="ERROR")

    async def _on_system_alert(self, data: dict):
        """处理系统告警"""
        await self.notify_admins(data.get("message", "System Alert"), level="WARNING")

    async def _on_security_alert(self, data: dict):
        """处理安全告警 (如多次登录失败)"""
        # 只有在达到一定阈值或特定条件时才通知，避免刷屏
        # 这里简单示例，每次失败都记录太吵，实际业务可能需要聚合
        # 为演示，暂时只处理标为 'critical' 的安全事件
        if data.get("severity") == "critical":
            msg = f"Security Alert: {data.get('message')}\nIP: {data.get('ip')}"
            await self.notify_admins(msg, level="WARNING")
