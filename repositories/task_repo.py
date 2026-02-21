from sqlalchemy import select, update, func
from models.models import TaskQueue, ForwardRule, Chat
from datetime import datetime, timedelta
import logging
from core.states import validate_transition
from core.config import settings
from core.helpers.db_utils import async_db_retry

logger = logging.getLogger(__name__)

class TaskRepository:
    def __init__(self, db):
        self.db = db

    async def archive_old_tasks(self, hot_days: int = 7, batch_size: int = 10000) -> dict:
        """归档旧任务记录。"""
        from core.archive.engine import UniversalArchiver
        from models.models import TaskQueue
        
        archiver = UniversalArchiver()
        result = await archiver.archive_table(
            model_class=TaskQueue,
            hot_days=hot_days,
            batch_size=batch_size
        )
        return result.to_dict()

    @async_db_retry(max_retries=5)
    async def push(self, task_type: str, payload: dict, priority: int = 0, scheduled_at: datetime = None):
        import json
        from sqlalchemy import insert
        
        # 提取用于去重的关键信息
        chat_id = payload.get('chat_id')
        message_id = payload.get('message_id')
        grouped_id = payload.get('grouped_id')
        
        unique_key = None
        if chat_id and message_id:
            unique_key = f"{task_type}:{chat_id}:{message_id}"

        from core.db_factory import AsyncSessionManager
        async with AsyncSessionManager() as session:
            # [Scheme 7 Optimization] 使用原子化 INSERT OR IGNORE 替代先查后增
            # 彻底解决多并发场景下的重复推送问题
            stmt = insert(TaskQueue).values(
                task_type=task_type,
                task_data=json.dumps(payload),
                unique_key=unique_key,
                grouped_id=str(grouped_id) if grouped_id else None,
                priority=priority,
                status='pending',
                scheduled_at=scheduled_at,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ).prefix_with('OR IGNORE')
            
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"✅ 任务入列成功 (Key: {unique_key})")
            else:
                if unique_key:
                    logger.warning(f"⚠️ 任务已存在，跳过入列: {unique_key}")
                else:
                    logger.warning("⚠️ 任务入列被忽略 (rowcount=0)")

    @async_db_retry(max_retries=5)
    async def push_batch(self, tasks_data: list):
        """
        批量写入任务 (Batch Insert)
        Args:
            tasks_data: List[(task_type, payload, priority)]
        """
        import json
        from sqlalchemy import insert
        
        if not tasks_data:
            return
            
        values_list = []
        now = datetime.utcnow()
        
        for task_type, payload, priority in tasks_data:
            chat_id = payload.get('chat_id')
            message_id = payload.get('message_id')
            grouped_id = payload.get('grouped_id')
            
            unique_key = None
            if chat_id and message_id:
                unique_key = f"{task_type}:{chat_id}:{message_id}"
            
            values_list.append({
                "task_type": task_type,
                "task_data": json.dumps(payload),
                "unique_key": unique_key,
                "grouped_id": str(grouped_id) if grouped_id else None,
                "priority": priority,
                "attempts": 0,
                "status": "pending",
                "created_at": now,
                "updated_at": now
            })

        if not values_list:
            return

        from core.db_factory import AsyncSessionManager
        async with AsyncSessionManager() as session:
             # 使用 Core Insert + OR IGNORE (SQLite) 实现高性能批量去重写入
             stmt = insert(TaskQueue).values(values_list).prefix_with('OR IGNORE')
             await session.execute(stmt)
             # AsyncSessionManager handles commit automatically
             logger.info(f"✅ 批量聚合写入: {len(values_list)} 条任务")

    @async_db_retry(max_retries=5)
    async def fetch_next(self, limit: int = 1):
        """
        获取下一批待处理任务。
        优化点：分两步执行，先只读查询候选 ID，再原子更新。这样可以缩短锁定时间。
        """
        from core.db_factory import AsyncSessionManager
        now = datetime.utcnow()
        # 预留 50ms 缓冲，确保不会因为微小的时钟差漏掉任务
        buffer_now = now + timedelta(milliseconds=50)
        lease_until = now + timedelta(seconds=settings.TASK_DISPATCHER_MAX_SLEEP + 60)
        
        # 1. 第一步：获取候选任务 ID (Read Phase - 不加锁)
        async with AsyncSessionManager(readonly=True) as session:
            stmt_candidates = (
                select(TaskQueue.id, TaskQueue.grouped_id)
                .where(
                    (TaskQueue.status == 'pending') |
                    (
                        (TaskQueue.status == 'running') & 
                        (TaskQueue.locked_until != None) & 
                        (TaskQueue.locked_until <= now)
                    )
                )
                .where((TaskQueue.scheduled_at == None) | (TaskQueue.scheduled_at <= buffer_now))
                .where((TaskQueue.next_retry_at == None) | (TaskQueue.next_retry_at <= buffer_now))
                .order_by(TaskQueue.priority.desc(), TaskQueue.created_at.asc())
                .limit(limit)
            )
            
            result = await session.execute(stmt_candidates)
            candidates = result.all() # List of Row(id, grouped_id)

        if not candidates:
            return []

        # 收集主任务 ID 和分组 ID
        candidate_ids = [c.id for c in candidates]
        group_ids = [c.grouped_id for c in candidates if c.grouped_id]
        
        final_task_ids = set(candidate_ids)
        
        # 2. 第二步：若存在 grouped_id，扩展并确定最终任务集合 (Read Phase - 不加锁)
        if group_ids:
            async with AsyncSessionManager(readonly=True) as session:
                stmt_groups = (
                    select(TaskQueue.id)
                    .where(TaskQueue.grouped_id.in_(group_ids))
                    .where(TaskQueue.status == 'pending')
                )
                group_result = await session.execute(stmt_groups)
                for row in group_result:
                    final_task_ids.add(row[0])

        final_task_ids = list(final_task_ids)
        
        # 3. 第三步：原子更新候选任务状态 (Write Phase - BEGIN IMMEDIATE)
        async with AsyncSessionManager() as session:
            stmt = (
                update(TaskQueue)
                .where(TaskQueue.id.in_(final_task_ids))
                .where(
                    (TaskQueue.status == 'pending') |
                    (
                        (TaskQueue.status == 'running') & 
                        (TaskQueue.locked_until <= now)
                    )
                )
                .values(
                    status='running',
                    started_at=now,
                    locked_until=lease_until, # 设置租约
                    updated_at=now
                )
                .execution_options(synchronize_session=False)
                .returning(TaskQueue)
            )
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            # [Fix] 如果在更新那一刻，某些任务状态变了，导致更新到的任务少于预期，是正常的
            # 这里的原子性由 .where(status.in_...) 保证
            if tasks:
                tasks.sort(key=lambda x: x.created_at)
                logger.debug(f"[TaskRepo] 成功锁定 {len(tasks)} 个任务 (请求: {len(final_task_ids)})")
            
            return tasks

    @async_db_retry(max_retries=5)
    async def complete(self, task_id: int):
        """标记任务完成 (纯 UPDATE，最小化锁持有时间)"""
        now = datetime.utcnow()
        async with self.db.get_session() as session:
            # [Optimization] 将状态验证内联到 WHERE 条件中，省去 SELECT 阶段
            # 合法的前置状态: running -> completed
            result = await session.execute(
                update(TaskQueue)
                .where(TaskQueue.id == task_id)
                .where(TaskQueue.status.in_(['running', 'pending']))
                .values(
                    status='completed',
                    completed_at=now,
                    updated_at=now
                )
            )
            await session.commit()
            if result.rowcount > 0:
                logger.info(f"任务完成: {task_id}")
            else:
                logger.warning(f"任务完成失败(状态不匹配或不存在): {task_id}")

    @async_db_retry(max_retries=5)
    async def fail(self, task_id: int, error: str):
        """标记任务失败 (纯 UPDATE，最小化锁持有时间)"""
        now = datetime.utcnow()
        error_str = str(error)
        async with self.db.get_session() as session:
            # [Optimization] 将状态验证内联到 WHERE 条件中，省去 SELECT 阶段
            # 合法的前置状态: running/pending -> failed
            result = await session.execute(
                update(TaskQueue)
                .where(TaskQueue.id == task_id)
                .where(TaskQueue.status.in_(['running', 'pending']))
                .values(
                    status='failed',
                    error_message=error_str,
                    updated_at=now
                )
            )
            await session.commit()
            
            if result.rowcount > 0:
                # 对于 "Source message not found" 这类预期内的业务情况,使用 DEBUG 级别
                if "Source message not found" in error_str:
                    logger.debug(f"任务失败: {task_id}, 错误: {error_str}")
                else:
                    logger.error(f"任务失败: {task_id}, 错误: {error_str}")
            else:
                logger.warning(f"任务失败标记跳过(状态不匹配或不存在): {task_id}")
            
    @async_db_retry(max_retries=5)
    async def fail_or_retry(self, task_id: int, error: str, max_retries: int = settings.MAX_RETRIES):
        """核心修复：失败重试机制"""
        async with self.db.get_session() as session:
            stmt = select(TaskQueue).where(TaskQueue.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            
            if task:
                now = datetime.utcnow()
                task.error_message = str(error)
                if task.attempts < max_retries:
                    if validate_transition(task.status, 'pending'):
                        task.attempts += 1
                        task.status = 'pending' # 重新放回队列
                        task.priority += 1      # 稍微提高优先级以便重试
                        # 实现指数退避算法：2^(attempts) 秒
                        backoff_seconds = 2 ** task.attempts
                        task.next_retry_at = now + timedelta(seconds=backoff_seconds)
                        task.updated_at = now
                        logger.info(f"任务重试: {task_id}, 重试次数: {task.attempts}, 下次重试时间: {task.next_retry_at}")
                else:
                    if validate_transition(task.status, 'failed'):
                        task.status = 'failed'  # 彻底失败
                        task.updated_at = now
                        logger.error(f"任务最终失败: {task_id}, 错误: {error}")
                await session.commit()
            
    @async_db_retry(max_retries=5)
    async def rescue_stuck_tasks(self, timeout_minutes: int = 10):
        """僵尸任务救援 - 将处于 'running' 状态超过指定时间的任务重置为 'pending'"""
        from core.db_factory import AsyncSessionManager
        async with AsyncSessionManager() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            now = datetime.utcnow()
            
            # 查找并重置僵尸任务
            # 只对状态为running且更新时间超过cutoff_time的任务进行操作
            stmt = update(TaskQueue).where(
                TaskQueue.status == 'running',
                TaskQueue.updated_at < cutoff_time
            ).values(
                status='pending',
                attempts=TaskQueue.attempts + 1, # 增加重试计数
                error_message=TaskQueue.error_message + ' [System] Task rescued from zombie state',
                updated_at=now
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"已救援 {result.rowcount} 个僵尸任务")
            return result.rowcount
            
    @async_db_retry(max_retries=5)
    async def reschedule(self, task_id: int, next_run_time: datetime):
        """重新调度任务 (纯 UPDATE，最小化锁持有时间)"""
        now = datetime.utcnow()
        async with self.db.get_session() as session:
            # [Optimization] 将状态验证内联到 WHERE 条件中
            # 合法的前置状态: running/pending/failed -> pending (reschedule)
            result = await session.execute(
                update(TaskQueue)
                .where(TaskQueue.id == task_id)
                .where(TaskQueue.status.in_(['running', 'pending', 'failed']))
                .values(
                    status='pending',
                    scheduled_at=next_run_time,
                    next_retry_at=next_run_time,
                    updated_at=now
                )
            )
            await session.commit()
            if result.rowcount > 0:
                logger.info(f"任务重新调度: {task_id}, 下次执行时间: {next_run_time}")
            else:
                logger.warning(f"任务调度跳过(状态不匹配或不存在): {task_id}")

    @async_db_retry(max_retries=5)
    async def fetch_group_tasks(self, grouped_id: str, exclude_task_id: int):
        """
        获取同一媒体组的其他相关任务，并原子锁定它们
        
        Args:
            grouped_id: 媒体组ID
            exclude_task_id: 当前已获取的任务ID（排除它）
            
        Returns:
            List[TaskQueue]: 相关任务列表
        """
        from core.db_factory import AsyncSessionManager
        async with AsyncSessionManager() as session:
            # [Optimization] 增加 30s 时间冗余，彻底根除时钟偏差导致的任务"不可见"问题
            now = datetime.utcnow() + timedelta(seconds=30)
            
            # 1. 查找同组的其他 pending 任务
            stmt = (
                select(TaskQueue.id)
                .where(TaskQueue.grouped_id == grouped_id)
                .where(TaskQueue.id != exclude_task_id)
                .where(TaskQueue.status == 'pending')  # 只获取 pending 的
                .order_by(TaskQueue.id.asc())
            )
            result = await session.execute(stmt)
            task_ids = result.scalars().all()
            
            if not task_ids:
                return []
                
            # 2. 原子锁定这些任务
            update_stmt = (
                update(TaskQueue)
                .where(TaskQueue.id.in_(task_ids))
                .values(
                    status='running',
                    started_at=now,
                    updated_at=now
                )
                .execution_options(synchronize_session=False)
                .returning(TaskQueue)
            )
            
            result = await session.execute(update_stmt)
            tasks = result.scalars().all()
            
            await session.commit()
            logger.info(f"🔒 原子锁定并获取媒体组任务: {len(tasks)} 个 (Group: {grouped_id})")
            return tasks

    @async_db_retry(max_retries=5)
    async def get_queue_status(self):
        """获取队列状态统计 (只读)"""
        async with self.db.get_session(readonly=True) as session:
            # 获取各状态任务数量
            stmt = select(TaskQueue.status, func.count()).group_by(TaskQueue.status)
            res = await session.execute(stmt)
            counts = dict(res.all())
            logger.info(f"🔍 [TaskRepository] DB Queue Status raw counts: {counts}")
            
            pending = counts.get('pending', 0)
            running = counts.get('running', 0)
            completed = counts.get('completed', 0)
            failed = counts.get('failed', 0)
            total = sum(counts.values())
            
            # 计算平均延迟 (最近 100 条完成的任务)
            from sqlalchemy import desc
            avg_delay = 0
            try:
                delay_stmt = (
                    select(TaskQueue.started_at, TaskQueue.created_at)
                    .where(TaskQueue.status == 'completed', TaskQueue.started_at != None)
                    .order_by(desc(TaskQueue.completed_at))
                    .limit(100)
                )
                results = (await session.execute(delay_stmt)).all()
                if results:
                    total_delay = sum((r.started_at - r.created_at).total_seconds() for r in results)
                    avg_delay = total_delay / len(results)
            except Exception: pass

            # 计算错误率
            err_rate = 0.0
            if completed + failed > 0:
                err_rate = (failed / (completed + failed)) * 100

            return {
                'active_queues': pending,
                'running_tasks': running,
                'total_tasks': total,
                'completed_tasks': completed,
                'failed_tasks': failed,
                'error_rate': f"{err_rate:.1f}%",
                'avg_delay': f"{avg_delay:.1f}s"
            }

    async def get_rule_stats(self):
        """获取规则统计信息 (只读)"""
        async with self.db.get_session(readonly=True) as session:
            # 获取总规则数和活跃规则数
            total_rules = await session.execute(
                select(func.count(ForwardRule.id))
            )
            active_rules = await session.execute(
                select(func.count(ForwardRule.id)).where(ForwardRule.enable_rule == True)
            )
            total_chats = await session.execute(
                select(func.count(Chat.id))
            )
            
            return {
                'total_rules': total_rules.scalar() or 0,
                'active_rules': active_rules.scalar() or 0,
                'total_chats': total_chats.scalar() or 0
            }

    async def get_tasks(self, page: int = 1, limit: int = 50, status: str = None, task_type: str = None):
        """分页获取任务列表 (只读)"""
        async with self.db.get_session(readonly=True) as session:
            # 构建查询
            stmt = select(TaskQueue)
            if status:
                stmt = stmt.where(TaskQueue.status == status)
            if task_type:
                stmt = stmt.where(TaskQueue.task_type == task_type)
            
            # 计算总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0
            
            # 排序和分页
            stmt = stmt.order_by(TaskQueue.priority.desc(), TaskQueue.created_at.desc())
            stmt = stmt.offset((page - 1) * limit).limit(limit)
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            return tasks, total

    async def get_task_by_id(self, task_id: int):
        """获取单个任务详情 (只读)"""
        async with self.db.get_session(readonly=True) as session:
            stmt = select(TaskQueue).where(TaskQueue.id == task_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()