from sqlalchemy import select, func
from models.models import User
from werkzeug.security import generate_password_hash
from schemas.user import UserDTO, UserAuthDTO
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, db):
        self.db = db

    async def get_user_by_username(self, username: str) -> Optional[UserDTO]:
        """根据用户名获取用户 (不含敏感信息)"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.username == username)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return UserDTO.model_validate(obj) if obj else None

    async def get_user_for_auth(self, username: str) -> Optional[UserAuthDTO]:
        """获取用户认证信息 (包含密码Hash等)"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.username == username)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return UserAuthDTO.model_validate(obj) if obj else None

    async def get_all_users(self) -> List[UserDTO]:
        """获取所有用户"""
        async with self.db.get_session() as session:
            stmt = select(User).order_by(User.id.asc())
            result = await session.execute(stmt)
            users = result.scalars().all()
            return [UserDTO.model_validate(u) for u in users]

    async def create_user(self, username: str, password: str, is_admin: bool = False):
        """创建用户"""
        async with self.db.get_session() as session:
            user = User(
                username=username,
                password=generate_password_hash(password),
                is_admin=is_admin,
                is_active=True,
                is_2fa_enabled=False,
                login_count=0
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return UserDTO.model_validate(user)

    async def update_user_admin_status(self, user_id: int, is_admin: bool):
        """更新用户管理员状态"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.is_admin = is_admin
                await session.commit()
                return UserDTO.model_validate(user)
            return None

    async def update_user_active_status(self, user_id: int, is_active: bool):
        """更新用户激活状态"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.is_active = is_active
                await session.commit()
                return UserDTO.model_validate(user)
            return None

    async def delete_user(self, user_id: int):
        """删除用户"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                await session.delete(user)
                await session.commit()
                return True
            return False

    async def update_user(self, user_id: int, **kwargs):
        """更新用户信息"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                await session.commit()
                return UserDTO.model_validate(user)
            return None

    async def get_user_by_id(self, user_id: int) -> Optional[UserDTO]:
        """根据ID获取用户"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return UserDTO.model_validate(obj) if obj else None
            
    async def get_user_auth_by_id(self, user_id: int) -> Optional[UserAuthDTO]:
        """根据ID获取用户认证信息 (包含密码Hash等)"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return UserAuthDTO.model_validate(obj) if obj else None

    async def get_user_count(self):
        """获取用户数量"""
        async with self.db.get_session() as session:
            stmt = select(func.count(User.id))
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_allow_registration(self) -> bool:
        """获取是否允许注册"""
        try:
            from core.config import settings
            mod = __import__('services.config_service', fromlist=['config_service'])
            config_service = mod.config_service
            v = await config_service.get('ALLOW_REGISTRATION')
            if v is None:
                 return settings.ALLOW_REGISTRATION
            return str(v).lower() in ('1', 'true', 'yes')
        except Exception:
            from core.config import settings
            return settings.ALLOW_REGISTRATION

    async def set_allow_registration(self, allow: bool) -> None:
        """设置是否允许注册"""
        mod = __import__('services.config_service', fromlist=['config_service'])
        config_service = mod.config_service
        await config_service.set('ALLOW_REGISTRATION', 'true' if allow else 'false', data_type='string')

    async def get_user_by_telegram_id(self, telegram_id: str) -> Optional[UserDTO]:
        """根据Telegram ID获取用户"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(User.telegram_id == str(telegram_id))
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return UserDTO.model_validate(obj) if obj else None

    async def get_admin_by_telegram_id(self, telegram_id: str) -> Optional[UserDTO]:
        """根据Telegram ID获取管理员用户"""
        async with self.db.get_session() as session:
            stmt = select(User).filter(
                User.telegram_id == str(telegram_id),
                User.is_admin == True,
                User.is_active == True
            )
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return UserDTO.model_validate(obj) if obj else None
