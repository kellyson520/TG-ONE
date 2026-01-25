"""
User Service
Handles user-related business logic and information retrieval.
"""
from typing import Optional, List
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

    async def is_admin(self, telegram_id: int) -> bool:
        """检查用户是否为管理员"""
        if not telegram_id:
            return False
            
        # 1. 检查环境变量配置的超级管理员
        import os
        admin_id = os.getenv("ADMIN_ID")
        if admin_id and str(telegram_id) == str(admin_id):
            return True
            
        # 2. 检查数据库
        try:
            user_dto = await self.container.user_repo.get_user_by_telegram_id(str(telegram_id))
            return user_dto.is_admin if user_dto else False
        except Exception as e:
            logger.error(f"Error checking admin status for {telegram_id}: {e}")
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

user_service = UserService()
