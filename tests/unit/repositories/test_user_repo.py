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
