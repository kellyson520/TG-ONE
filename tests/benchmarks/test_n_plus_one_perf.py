import asyncio
import time
import sys
import os
from pathlib import Path
from sqlalchemy import select, text
from unittest.mock import AsyncMock

# 路径修复
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.container import container
from models.models import ForwardRule, RuleSync, Chat

class QueryCounter:
    """SQLAlchemy 查询计数器"""
    def __init__(self):
        self.count = 0
    
    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        if not statement.startswith("SAVEPOINT"):
            self.count += 1

async def benchmark_rule_sync_after():
    """测试修复后的同步规则性能"""
    print("\n--- 性能基准测试: Rule Sync (验证修复后) ---")
    
    from handlers.button.callback.modules.rule_settings import update_rule_setting
    
    async with container.db.session() as session:
        # 清理并准备数据
        await session.execute(text("DELETE FROM rule_syncs"))
        await session.execute(text("DELETE FROM forward_rules"))
        await session.execute(text("DELETE FROM chats"))
        
        source = Chat(telegram_chat_id="100", name="Source")
        target = Chat(telegram_chat_id="200", name="Target")
        session.add_all([source, target])
        await session.flush()
        
        main_rule = ForwardRule(source_chat_id=source.id, target_chat_id=target.id, enable_sync=True)
        session.add(main_rule)
        await session.flush()
        
        for i in range(10):
            r = ForwardRule(source_chat_id=source.id, target_chat_id=target.id)
            session.add(r)
            await session.flush()
            session.add(RuleSync(rule_id=main_rule.id, sync_rule_id=r.id))
        
        await session.commit()
        main_rule_id = main_rule.id

    # 挂载计数器
    from sqlalchemy import event
    counter = QueryCounter()
    engine = container.db.engine
    event.listen(engine.sync_engine, "before_cursor_execute", counter)
    
    mock_event = AsyncMock()
    # Mock event.answer
    mock_event.answer = AsyncMock()
    
    mock_message = AsyncMock()
    mock_message.edit = AsyncMock()
    
    config = {"toggle_func": lambda x: not x, "display_name": "测试"}
    
    start_time = time.time()
    # 调用实际的修复后的函数
    await update_rule_setting(mock_event, main_rule_id, mock_message, "enable_rule", config, "rule")
    duration = time.time() - start_time

    print(f"执行耗时: {duration:.4f}s")
    print(f"总查询次数: {counter.count}")
    
    event.remove(engine.sync_engine, "before_cursor_execute", counter)
    
    # 验证数据库是否已更新
    async with container.db.session() as session:
        result = await session.execute(select(ForwardRule))
        all_rules = result.scalars().all()
        true_count = sum(1 for r in all_rules if r.enable_rule is True)
        print(f"验证：共有 {len(all_rules)} 条规则，其中 {true_count} 条已同步更新")
        
    return counter.count, duration

if __name__ == "__main__":
    os.environ["ENV"] = "dev"
    asyncio.run(benchmark_rule_sync_after())
