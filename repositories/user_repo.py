from sqlalchemy import select, func
from models.models import User
from werkzeug.security import generate_password_hash

class UserRepository:
    def __init__(self, db):
        self.db = db

    async def get_user_by_username(self, username: str):
        """根据用户名获取用户"""
        async with self.db.session() as session:
            stmt = select(User).filter(User.username == username)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_users(self):
        """获取所有用户"""
        async with self.db.session() as session:
            stmt = select(User).order_by(User.id.asc())
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create_user(self, username: str, password: str, is_admin: bool = False):
        """创建用户"""
        async with self.db.session() as session:
            user = User(
                username=username,
                password=generate_password_hash(password),
                is_admin=is_admin
            )
            session.add(user)
            await session.commit()
            return user

    async def update_user_admin_status(self, user_id: int, is_admin: bool):
        """更新用户管理员状态"""
        async with self.db.session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.is_admin = is_admin
                await session.commit()
                return user
            return None

    async def update_user_active_status(self, user_id: int, is_active: bool):
        """更新用户激活状态"""
        async with self.db.session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.is_active = is_active
                await session.commit()
                return user
            return None

    async def delete_user(self, user_id: int):
        """删除用户"""
        async with self.db.session() as session:
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
        async with self.db.session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                await session.commit()
                return user
            return None

    async def get_user_by_id(self, user_id: int):
        """根据ID获取用户"""
        async with self.db.session() as session:
            stmt = select(User).filter(User.id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_count(self):
        """获取用户数量"""
        async with self.db.session() as session:
            stmt = select(func.count(User.id))
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_allow_registration(self) -> bool:
        """获取是否允许注册"""
        # 这里应该从配置服务获取，暂时返回默认值
        from services.config_service import config_service
        v = await config_service.get('ALLOW_REGISTRATION')
        if v is None:
             import os
             v = os.getenv('ALLOW_REGISTRATION', 'false')
        return str(v).lower() in ('1', 'true', 'yes')

    async def set_allow_registration(self, allow: bool) -> None:
        """设置是否允许注册"""
        from services.config_service import config_service
        await config_service.set('ALLOW_REGISTRATION', 'true' if allow else 'false', data_type='string')
