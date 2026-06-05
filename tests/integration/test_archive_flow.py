import asyncio
import os
import sys
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.config import settings
from repositories.db_context import async_db_session
from models.models import (
    RuleLog, ForwardRule, ErrorLog, Chat
)
from repositories.archive_manager import get_archive_manager

async def setup_test_data():
    async with async_db_session() as session:
        # Check if we have source/target chats
        source_chat = (await session.execute(select(Chat).where(Chat.telegram_chat_id == "123"))).scalar()
        if not source_chat:
            source_chat = Chat(telegram_chat_id="123", title="Source Chat")
            session.add(source_chat)
        
        target_chat = (await session.execute(select(Chat).where(Chat.telegram_chat_id == "456"))).scalar()
        if not target_chat:
            target_chat = Chat(telegram_chat_id="456", title="Target Chat")
            session.add(target_chat)
            
        await session.commit()
        await session.refresh(source_chat)
        await session.refresh(target_chat)

        # Check if we have at least one rule to associate logs with
        res = await session.execute(select(ForwardRule).limit(1))
        rule = res.scalar()
        if not rule:
            # Create a dummy rule
            rule = ForwardRule(description="Test Rule", source_chat_id=source_chat.id, target_chat_id=target_chat.id)
            session.add(rule)
            await session.commit()
            await session.refresh(rule)
        
        # Create 10 old logs (e.g., 40 days ago)
        old_date = datetime.utcnow() - timedelta(days=40)
        logs = []
        for i in range(10):
            logs.append(RuleLog(
                rule_id=rule.id,
                action="forwarded",
                details=f"Archive test log {i}",
                created_at=old_date
            ))
        session.add_all(logs)
        await session.commit()
        
        # Add some old error logs
        old_errors = []
        for i in range(5):
            old_errors.append(ErrorLog(
                level="ERROR",
                module="test",
                message=f"Test error {i}",
                created_at=old_date.isoformat()
            ))
        session.add_all(old_errors)
        await session.commit()
        
        return rule.id

@pytest.mark.asyncio
async def test_archive_flow_integration():
    """归档全链路集成测试"""
    print("\nStarting Archive Flow Integration Test...")
    rule_id = await setup_test_data()
    
    print(f"DEBUG: ARCHIVE_ROOT = {settings.ARCHIVE_ROOT}")
    print(f"DEBUG: rule_id = {rule_id}")
    
    manager = get_archive_manager(async_db_session)
    await manager.initialize()
    
    # 记录初始数量
    async with async_db_session() as session:
        initial_count = (await session.execute(select(func.count(RuleLog.id)))).scalar()
        print(f"DEBUG: initial_count = {initial_count}")
        assert initial_count >= 10
    
    # 执行归档
    await manager.run_archiving_cycle()
    
    # 验证 SQLite 中数据已删除
    async with async_db_session() as session:
        final_count = (await session.execute(select(func.count(RuleLog.id)))).scalar()
        final_err_count = (await session.execute(select(func.count(ErrorLog.id)))).scalar()
        assert final_count < initial_count
        assert final_err_count == 0  # 刚才创建的 5 条应该都被归档了
    
    # 验证跨库查询
    combined_logs = await manager.get_combined_logs(rule_id=rule_id, limit=20)
    assert len(combined_logs) >= 10
    
    # 验证 Bloom 索引
    from repositories.bloom_index import bloom
    # 注意：归档 MediaSignature 逻辑类似，这里也可以加，但 test_data 里没加 MediaSignature
    # 不过 ArchiveManager 逻辑是对称的
    
    print("Archive Flow Integration Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_archive_flow_integration())
