import pytest
from repositories.user_repo import UserRepository

@pytest.fixture
def user_repo(container):
    return UserRepository(container.db)

@pytest.mark.asyncio
@pytest.mark.usefixtures("clear_data")
class TestUserRepository:
    async def test_create_and_get_user(self, user_repo):
        # 1. 创建用户
        user = await user_repo.create_user("testrepo", "password123", is_admin=True)
        assert user.id is not None
        assert user.username == "testrepo"
        assert user.is_admin is True
        
        # 2. 获取用户
        fetched = await user_repo.get_user_by_username("testrepo")
        assert fetched is not None
        assert fetched.id == user.id
        
        # 3. 根据ID获取
        fetched_by_id = await user_repo.get_user_by_id(user.id)
        assert fetched_by_id.username == "testrepo"

    async def test_get_all_users_and_count(self, user_repo):
        await user_repo.create_user("user1", "p1")
        await user_repo.create_user("user2", "p2")
        
        users = await user_repo.get_all_users()
        count = await user_repo.get_user_count()
        
        assert len(users) >= 2
        assert count >= 2

    async def test_update_user_status(self, user_repo):
        user = await user_repo.create_user("teststatus", "p")
        
        # 更新管理员状态
        updated = await user_repo.update_user_admin_status(user.id, True)
        assert updated.is_admin is True
        
        # 更新激活状态
        updated = await user_repo.update_user_active_status(user.id, False)
        assert updated.is_active is False

    async def test_delete_user(self, user_repo):
        user = await user_repo.create_user("testdelete", "p")
        
        success = await user_repo.delete_user(user.id)
        assert success is True
        
        # 验证已删除
        fetched = await user_repo.get_user_by_id(user.id)
        assert fetched is None

    async def test_update_user_generic(self, user_repo):
        user = await user_repo.create_user("testupdate", "p")
        
        await user_repo.update_user(user.id, username="newname", is_admin=True)
        
        updated = await user_repo.get_user_by_id(user.id)
        assert updated.username == "newname"
        assert updated.is_admin is True

    async def test_telegram_id_methods(self, user_repo):
        # 1. 创建带 Telegram ID 的用户
        user = await user_repo.create_user("tg_user", "p")
        await user_repo.update_user(user.id, telegram_id="123456789")
        
        # 2. 根据 Telegram ID 获取
        fetched = await user_repo.get_user_by_telegram_id("123456789")
        assert fetched is not None
        assert fetched.username == "tg_user"
        
        # 3. 创建管理员并根据 Telegram ID 获取
        admin = await user_repo.create_user("tg_admin", "p", is_admin=True)
        await user_repo.update_user(admin.id, telegram_id="987654321")
        
        fetched_admin = await user_repo.get_admin_by_telegram_id("987654321")
        assert fetched_admin is not None
        assert fetched_admin.username == "tg_admin"
        assert fetched_admin.is_admin is True

    async def test_registration_settings(self, user_repo):
        # 注意：这里涉及到 config_service 的 mock 或真实调用
        # UserRepository 内部使用了 __import__ 动态加载
        original = await user_repo.get_allow_registration()
        
        await user_repo.set_allow_registration(not original)
        new_val = await user_repo.get_allow_registration()
        assert new_val != original
        
        # 恢复
        await user_repo.set_allow_registration(original)

    async def test_user_auth_dto(self, user_repo):
        user = await user_repo.create_user("auth_user", "password123")
        
        # 获取认证信息
        auth_data = await user_repo.get_user_for_auth("auth_user")
        assert auth_data is not None
        assert auth_data.password.startswith("pbkdf2:sha256") or auth_data.password.startswith("scrypt")
        
        auth_data_by_id = await user_repo.get_user_auth_by_id(user.id)
        assert auth_data_by_id.id == user.id
        assert auth_data_by_id.username == "auth_user"
