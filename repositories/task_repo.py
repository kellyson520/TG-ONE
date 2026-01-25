from sqlalchemy import select, update, func
from models.models import TaskQueue, ForwardRule, Chat
from datetime import datetime, timedelta
import logging
from core.states import validate_transition
from core.config import settings

logger = logging.getLogger(__name__)

class TaskRepository:
    def __init__(self, db):
        self.db = db

    async def push(self, task_type: str, payload: dict, priority: int = 0, scheduled_at: datetime = None):
        import json
        
        # 提取用于去重的关键信息
        chat_id = payload.get('chat_id')
        message_id = payload.get('message_id')
        grouped_id = payload.get('grouped_id')  # 提取 grouped_id
        
        unique_key = None
        if chat_id and message_id:
            unique_key = f"{task_type}:{chat_id}:{message_id}"

        async with self.db.session() as session:
            # 检查去重
            if unique_key:
                exists = await session.execute(
                    select(TaskQueue.id).where(TaskQueue.unique_key == unique_key)
                )
                if exists.scalar():
                    logger.warning(f"⚠️ 任务已存在，跳过入列: {unique_key}")
                    return # 幂等返回，不报错

            task = TaskQueue(
                task_type=task_type, 
                task_data=json.dumps(payload),
                unique_key=unique_key, # 存入唯一键
                grouped_id=str(grouped_id) if grouped_id else None, # 存入 grouped_id
                priority=priority,
                retry_count=0,
                scheduled_at=scheduled_at  # 直接使用datetime对象，不再转换为字符串
            )
            session.add(task)
            await session.commit()
            logger.info(f"✅ 任务入列: {task.id} (Key: {unique_key})")

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
                "retry_count": 0,
                "status": "pending",
                "created_at": now,
                "updated_at": now
            })

        if not values_list:
            return

        async with self.db.session() as session:
             # 使用 Core Insert + OR IGNORE (SQLite) 实现高性能批量去重写入
             try:
                 stmt = insert(TaskQueue).values(values_list).prefix_with('OR IGNORE')
                 await session.execute(stmt)
                 await session.commit()
                 logger.info(f"✅ 批量聚合写入: {len(values_list)} 条任务")
             except Exception as e:
                 logger.error(f"批量写入失败: {e}")
                 # Fallback: 如果批量失败（罕见），可以考虑逐条重试，或者直接抛出
                 raise

    async def fetch_next(self):
        """[Scheme 7 Standard] 原子化拉取任务
        使用 UPDATE ... RETURNING 确保取出任务的同时锁定状态，
        彻底根除多 Worker 并发下的竞态条件。
        """
        async with self.db.session() as session:
            now = datetime.utcnow()
            
            # 构造子查询：查找优先级最高、最老的待处理任务 ID
            # 注意：SQLite 的 UPDATE FROM 语法或子查询支持
            subquery = (
                select(TaskQueue.id)
                .where(TaskQueue.status == 'pending')
                .where((TaskQueue.scheduled_at == None) | (TaskQueue.scheduled_at <= now))
                .where((TaskQueue.next_retry_at == None) | (TaskQueue.next_retry_at <= now))
                .order_by(TaskQueue.priority.desc(), TaskQueue.created_at.asc())
                .limit(1)
                .scalar_subquery()
            )

            # 原子执行：更新状态并返回被更新的行
            # 这是一条 SQL 语句，数据库保证了原子性
            stmt = (
                update(TaskQueue)
                .where(TaskQueue.id == subquery)
                .values(
                    status='running',
                    started_at=now,
                    updated_at=now
                )
                .execution_options(synchronize_session=False)
                .returning(TaskQueue)  # 关键：直接返回对象
            )

            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            
            if task:
                await session.commit()
                logger.info(f"🔒 原子锁定并获取任务: {task.id}, 类型: {task.task_type}")
                return task
            
            return None

    async def complete(self, task_id: int):
        async with self.db.session() as session:
            # 先获取当前状态进行验证
            result = await session.execute(
                select(TaskQueue.status).where(TaskQueue.id == task_id)
            )
            current_status = result.scalar_one_or_none()
            
            if current_status and validate_transition(current_status, 'completed'):
                now = datetime.utcnow()
                await session.execute(
                    update(TaskQueue).where(TaskQueue.id == task_id).values(
                        status='completed',
                        completed_at=now,
                        updated_at=now
                    )
                )
                await session.commit()
                logger.info(f"任务完成: {task_id}")
            else:
                logger.warning(f"Invalid state transition for task {task_id}: {current_status} -> completed")

    async def fail(self, task_id: int, error: str):
        async with self.db.session() as session:
            # 先获取当前状态进行验证
            result = await session.execute(
                select(TaskQueue.status).where(TaskQueue.id == task_id)
            )
            current_status = result.scalar_one_or_none()
            
            if current_status and validate_transition(current_status, 'failed'):
                now = datetime.utcnow()
                await session.execute(
                    update(TaskQueue).where(TaskQueue.id == task_id).values(
                        status='failed', 
                        error_log=str(error),
                        updated_at=now
                    )
                )
                await session.commit()
                
                # 对于 "Source message not found" 这类预期内的业务情况,使用 DEBUG 级别
                # 避免触发错误告警和日志循环
                if "Source message not found" in str(error):
                    logger.debug(f"任务失败: {task_id}, 错误: {error}")
                else:
                    logger.error(f"任务失败: {task_id}, 错误: {error}")
            else:
                logger.warning(f"Invalid state transition for task {task_id}: {current_status} -> failed")
            
    async def fail_or_retry(self, task_id: int, error: str, max_retries: int = settings.MAX_RETRIES):
        """核心修复：失败重试机制"""
        async with self.db.session() as session:
            stmt = select(TaskQueue).where(TaskQueue.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            
            if task:
                now = datetime.utcnow()
                task.error_log = str(error)
                if task.retry_count < max_retries:
                    if validate_transition(task.status, 'pending'):
                        task.retry_count += 1
                        task.status = 'pending' # 重新放回队列
                        task.priority += 1      # 稍微提高优先级以便重试
                        # 实现指数退避算法：2^(retry_count) 秒
                        backoff_seconds = 2 ** task.retry_count
                        task.next_retry_at = now + timedelta(seconds=backoff_seconds)
                        task.updated_at = now
                        logger.info(f"任务重试: {task_id}, 重试次数: {task.retry_count}, 下次重试时间: {task.next_retry_at}")
                else:
                    if validate_transition(task.status, 'failed'):
                        task.status = 'failed'  # 彻底失败
                        task.updated_at = now
                        logger.error(f"任务最终失败: {task_id}, 错误: {error}")
                await session.commit()
            
    async def rescue_stuck_tasks(self, timeout_minutes: int = 10):
        """僵尸任务救援 - 将处于 'running' 状态超过指定时间的任务重置为 'pending'"""
        async with self.db.session() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            now = datetime.utcnow()
            
            # 查找并重置僵尸任务
            # 只对状态为running且更新时间超过cutoff_time的任务进行操作
            stmt = update(TaskQueue).where(
                TaskQueue.status == 'running',
                TaskQueue.updated_at < cutoff_time
            ).values(
                status='pending',
                retry_count=TaskQueue.retry_count + 1, # 增加重试计数
                error_log=TaskQueue.error_log + ' [System] Task rescued from zombie state',
                updated_at=now
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"已救援 {result.rowcount} 个僵尸任务")
            return result.rowcount
            
    async def reschedule(self, task_id: int, next_run_time: datetime):
        """重新调度任务，设置下次执行时间"""
        async with self.db.session() as session:
            # 先获取当前状态进行验证
            result = await session.execute(
                select(TaskQueue.status).where(TaskQueue.id == task_id)
            )
            current_status = result.scalar_one_or_none()
            
            if current_status and validate_transition(current_status, 'pending'):
                now = datetime.utcnow()
                await session.execute(
                    update(TaskQueue).where(TaskQueue.id == task_id).values(
                        status='pending',
                        scheduled_at=next_run_time,
                        next_retry_at=next_run_time,  # 更新下次重试时间
                        updated_at=now
                    )
                )
                await session.commit()
                logger.info(f"任务重新调度: {task_id}, 下次执行时间: {next_run_time}")
            else:
                logger.warning(f"Invalid state transition for task {task_id}: {current_status} -> pending (reschedule)")

    async def fetch_group_tasks(self, grouped_id: str, exclude_task_id: int):
        """
        获取同一媒体组的其他相关任务，并原子锁定它们
        
        Args:
            grouped_id: 媒体组ID
            exclude_task_id: 当前已获取的任务ID（排除它）
            
        Returns:
            List[TaskQueue]: 相关任务列表
        """
        async with self.db.session() as session:
            now = datetime.utcnow()
            
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

    async def get_queue_status(self):
        """获取队列状态统计"""
        async with self.db.session() as session:
            # 获取各状态任务数量
            pending_count = await session.execute(
                select(func.count()).where(TaskQueue.status == 'pending')
            )
            completed_count = await session.execute(
                select(func.count()).where(TaskQueue.status == 'completed')
            )
            failed_count = await session.execute(
                select(func.count()).where(TaskQueue.status == 'failed')
            )
            total_count = await session.execute(
                select(func.count(TaskQueue.id))
            )
            
            pending = pending_count.scalar() or 0
            completed = completed_count.scalar() or 0
            failed = failed_count.scalar() or 0
            total = total_count.scalar() or 0
            
            # 计算错误率
            err_rate = 0.0
            if completed + failed > 0:
                err_rate = (failed / (completed + failed)) * 100
            
            return {
                'active_queues': pending,
                'total_tasks': total,
                'completed_tasks': completed,
                'failed_tasks': failed,
                'error_rate': f"{err_rate:.1f}%"
            }

    async def get_rule_stats(self):
        """获取规则统计信息"""
        async with self.db.session() as session:
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

    async def get_tasks(self, page: int = 1, limit: int = 50, status: str = None):
        """分页获取任务列表"""
        async with self.db.session() as session:
            # 构建查询
            stmt = select(TaskQueue)
            if status:
                stmt = stmt.where(TaskQueue.status == status)
            
            # 计算总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0
            
            # 排序和分页
            stmt = stmt.order_by(TaskQueue.priority.desc(), TaskQueue.created_at.desc())
            stmt = stmt.offset((page - 1) * limit).limit(limit)
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            return tasks, total