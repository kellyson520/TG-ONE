import pytest
from models.models import User
from sqlalchemy import select

@pytest.mark.asyncio
async def test_create_user(db):
    """测试创建用户"""
    user = User(username="unit_test_user", password="secret")
    db.add(user)
    await db.commit()
    
    result = await db.execute(select(User).filter_by(username="unit_test_user"))
    fetched = result.scalar_one()
    
    assert fetched.username == "unit_test_user"
    assert fetched.id is not None

