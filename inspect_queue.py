
import asyncio
import sys
import os
from datetime import datetime

# 确保脚本可以引用项目本地模块
sys.path.append(os.getcwd())

from core.container import container
from models.models import TaskQueue
from sqlalchemy import select, func, desc

async def inspect():
    print("=" * 60)
    print(f"🔍 TG-ONE 任务队列深度巡检工具")
    print(f"📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    async with container.db.get_session(readonly=True) as session:
        # 1. 统计各状态分布
        stmt_counts = select(TaskQueue.status, func.count()).group_by(TaskQueue.status)
        res_counts = await session.execute(stmt_counts)
        counts = dict(res_counts.all())
        
        print(f"📊 状态统计:")
        print(f"  - ⏳ 等待中 (pending):    {counts.get('pending', 0)}")
        print(f"  - 🚀 运行中 (running):    {counts.get('running', 0)}")
        print(f"  - ✅ 已完成 (completed):  {counts.get('completed', 0)}")
        print(f"  - ❌ 失败 (failed):       {counts.get('failed', 0)}")
        print("-" * 60)

        # 2. 如果有积压，显示最早的 5 条等待任务
        if counts.get('pending', 0) > 0:
            print(f"🕒 最早的等待任务 (TOP 5):")
            stmt_pending = (
                select(TaskQueue)
                .where(TaskQueue.status == 'pending')
                .order_by(TaskQueue.priority.desc(), TaskQueue.created_at.asc())
                .limit(5)
            )
            res_pending = await session.execute(stmt_pending)
            for t in res_pending.scalars():
                # 处理可能的时间戳计算（统一为 UTC）
                now = datetime.utcnow()
                created = t.scheduled_at or t.created_at
                wait_time_sec = (now - created).total_seconds() if created else 0
                
                print(f"  [ID:{t.id}] 类型: {t.task_type} | 优先级: {t.priority}")
                print(f"           已等待: {wait_time_sec:.1f}s | 尝试次数: {t.attempts}")
                if t.error_message:
                    print(f"           上次错误: {t.error_message[:50]}...")
            print("-" * 60)

        # 3. 显示最近 5 条执行详情（包含失败描述）
        print(f"🔄 最近活动记录 (Latest 5):")
        stmt_latest = (
            select(TaskQueue)
            .order_by(desc(TaskQueue.updated_at))
            .limit(5)
        )
        res_latest = await session.execute(stmt_latest)
        for t in res_latest.scalars():
            status_emoji = "✅" if t.status == 'completed' else "❌" if t.status == 'failed' else "🚀" if t.status == 'running' else "⏳"
            print(f"  {status_emoji} ID:{t.id} | {t.task_type} | 状态: {t.status}")
            if t.status == 'failed' and t.error_message:
                print(f"     错误: {t.error_message}")
            if t.completed_at and t.started_at:
                duration = (t.completed_at - t.started_at).total_seconds()
                print(f"     耗时: {duration:.2f}s")

    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(inspect())
    except Exception as e:
        print(f"❌ 运行失败: {e}")
