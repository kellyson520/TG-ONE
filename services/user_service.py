"""
User Service
Handles user-related business logic and information retrieval.
"""
from typing import Optional, List, Any
import logging
from sqlalchemy import select
from models.models import User
from schemas.user import UserDTO

logger = logging.getLogger(__name__)

class UserService:
    @property
    def container(self):
        from core.container import container
        return container

    async def is_admin(self, telegram_id: int, event: Any = None, client: Any = None) -> bool:
        """
        检查用户是否为管理员。
        
        逻辑顺序:
        1. 环境变量 ADMINS 列表
        2. 数据库 User 表 is_admin 字段
        3. 如果提供 event 且为频道，检查机器人管理员是否为该频道的管理员 (Telethon 逻辑)
        
        Args:
            telegram_id: Telegram 用户 ID
            event: 可选，Telethon 事件对象 (用于检查频道权限)
            client: 可选，Telethon 客户端
        """
        if not telegram_id:
            return False

        # 1. 检查环境变量配置的管理员列表
        from core.helpers.common import get_admin_list
        try:
            bot_admins = get_admin_list()
            if telegram_id in bot_admins:
                logger.debug(f"用户 {telegram_id} 在.env管理员列表中")
                return True
        except Exception as e:
            logger.warning(f"获取.env管理员列表失败: {e}")

        # 2. 检查数据库
        try:
            user_dto = await self.container.user_repo.get_admin_by_telegram_id(str(telegram_id))
            if user_dto:
                logger.debug(f"用户 {telegram_id} 在数据库管理员列表中")
                return True
        except Exception as e:
            logger.error(f"Error checking admin status in DB for {telegram_id}: {e}")

        # 3. 检查频道管理员状态 (针对特定的 Telethon Event)
        if event and hasattr(event, "message"):
            message = event.message
            if message.is_channel and not message.is_group:
                try:
                    from core.helpers.common import get_channel_admins
                    if not client:
                        client = self.container.user_client
                        
                    channel_admins = await get_channel_admins(client, event.chat_id)
                    if channel_admins is not None:
                        bot_admins = get_admin_list()
                        # 检查机器人管理员是否在频道管理员列表中
                        admin_in_channel = any(admin_id in channel_admins for admin_id in bot_admins)
                        if admin_in_channel:
                            return True
                except Exception as e:
                    logger.error(f"检查频道管理员权限时出错: {e}")

        return False

    async def get_user_by_id(self, user_id: int) -> Optional[UserDTO]:
        """获取用户信息"""
        return await self.container.user_repo.get_user_by_id(user_id)

    async def get_all_users(self) -> List[UserDTO]:
        """获取所有用户 (Admin Only)"""
        # This should ideally use UserRepository.get_all
        async with self.container.db.session() as session:
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()
            return [UserDTO.model_validate(u) for u in users]

    async def process_user_info(self, event: Any, rule_id: int, message_text: str) -> str:
        """处理用户信息过滤与前缀添加"""
        try:
            from services.batch_user_service import get_batch_user_service
            from core.helpers.common import get_sender_info
            
            batch_service = get_batch_user_service()

            user_info_text = await batch_service.format_user_info_for_message(event)
            if user_info_text:
                return f"{user_info_text}{message_text}"

            username = await get_sender_info(event, rule_id)
            if username:
                return f"{username}:\n{message_text}"
            return message_text
        except Exception as e:
            logger.error(f"处理用户信息失败: {str(e)}")
            return message_text

user_service = UserService()
