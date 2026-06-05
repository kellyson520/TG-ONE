"""
任务查询服务层 (原生异步版)
提供 TaskQueue 历史任务相关的查询能力
"""
from typing import Dict, Any, List, Optional
import json
import logging
from sqlalchemy import select
# [Refactor Fix] 更新为使用 container
from core.container import container
from models.models import TaskQueue

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self):
        from core.archive.bridge import UnifiedQueryBridge
        self.bridge = UnifiedQueryBridge()

    async def list_tasks(self, task_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """列出最近的任务 (支持热冷联邦查询)"""
        logger.info(f"[TaskService] 开始跨层列出任务，类型={task_type}，限制={limit}")
        
        try:
            rows = await self.bridge.list_tasks(status=None, task_type=task_type, limit=limit)
                
            tasks = []
            for r in rows:
                try:
                    task_data_raw = r.get('task_data')
                    data = json.loads(task_data_raw) if task_data_raw else {}
                except Exception as json_err:
                    logger.warning(f"[TaskService] 解析任务数据失败，ID={r.get('id')}，错误={json_err}")
                    data = {}
                
                task_info = {
                    'id': r.get('id'),
                    'status': r.get('status'),
                    'started_at': r.get('started_at'),
                    'completed_at': r.get('completed_at'),
                    'forwarded': r.get('forwarded_count') or data.get('forwarded', 0),
                    'filtered': r.get('filtered_count') or data.get('filtered', 0),
                    'failed': r.get('failed_count') or data.get('failed', 0),
                    'total': r.get('total_count') or data.get('total', 0),
                }
                tasks.append(task_info)
                
            logger.info(f"[TaskService] 成功列出 {len(tasks)} 个任务")
            return {'success': True, 'tasks': tasks}
        except Exception as e:
            logger.error(f"[TaskService] 列出任务失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'tasks': []}

    async def list_recent_history_tasks(self, limit: int = 10) -> Dict[str, Any]:
        """列出最近的历史转发任务 (原生异步) - 兼容旧接口"""
        return await self.list_tasks(task_type='history_forward', limit=limit)

    async def get_task_detail(self, task_id: Optional[int] = None, task_type: Optional[str] = None) -> Dict[str, Any]:
        """获取任务详情 (支持热冷联邦查询)"""
        try:
            if task_id is not None:
                row = await self.bridge.get_task_detail(task_id)
            else:
                rows = await self.bridge.list_tasks(task_type=task_type, limit=1)
                row = rows[0] if rows else None
            
            if not row:
                return {'success': False, 'error': '未找到任务'}
            try:
                task_data_raw = row.get('task_data')
                data = json.loads(task_data_raw) if task_data_raw else {}
            except Exception as e:
                logger.warning(f"[TaskService] Failed to parse task_data: {e}")
                data = {}
            detail = {
                'id': row.get('id'),
                'status': row.get('status'),
                'started_at': row.get('started_at'),
                'completed_at': row.get('completed_at'),
                'data': {
                    **data,
                    'done': row.get('done_count') or data.get('done', 0),
                    'total': row.get('total_count') or data.get('total', 0),
                    'forwarded': row.get('forwarded_count') or data.get('forwarded', 0),
                    'filtered': row.get('filtered_count') or data.get('filtered', 0),
                    'failed': row.get('failed_count') or data.get('failed', 0),
                    'last_id': row.get('last_message_id') or data.get('last_id'),
                    'source_chat_id': row.get('source_chat_id') or data.get('source_chat_id'),
                    'target_chat_id': row.get('target_chat_id') or data.get('target_chat_id'),
                },
            }
            return {'success': True, 'task': detail}
        except Exception as e:
            logger.error(f"获取任务详情失败: {e}")
            return {'success': False, 'error': str(e)}

    async def get_history_task_detail(self, task_id: Optional[int] = None) -> Dict[str, Any]:
        """获取历史任务详情 (原生异步) - 兼容旧接口"""
        return await self.get_task_detail(task_id=task_id, task_type='history_forward')

    async def get_recent_failed_samples(self, limit: int = 20, task_type: Optional[str] = 'history_forward') -> Dict[str, Any]:
        """获取最近任务的失败样本 (原生异步)"""
        try:
            async with container.db.get_session() as session:
                stmt = select(TaskQueue).order_by(TaskQueue.id.desc()).limit(1)
                if task_type:
                    stmt = stmt.filter(TaskQueue.task_type == task_type)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
            failed_ids: List[int] = []
            if row and row.task_data:
                try:
                    data = json.loads(row.task_data)
                    failed_list = data.get('failed_ids', [])
                    if isinstance(failed_list, list):
                        failed_ids = failed_list[:limit]
                except Exception as e:
                    logger.debug(f"[TaskService] Parse failed_ids error: {e}")
            return {'success': True, 'failed_ids': failed_ids}
        except Exception as e:
            logger.error(f"获取失败样本失败: {e}")
            return {'success': False, 'error': str(e), 'failed_ids': []}

    async def schedule_custom_task(self, callback_info: Dict, delay_seconds: float, task_id: Optional[str] = None, max_retries: int = 3) -> str:
        """安排自定义任务 (注: callback_info 必须是可 JSON 序列化的)"""
        import time
        if task_id is None: task_id = f"custom_{time.time()}_{id(callback_info)}"
        
        # 验证序列化
        try:
            json.dumps(callback_info)
        except TypeError as e:
            logger.error(f"[TaskService] schedule_custom_task 失败: callback_info 不可序列化: {e}")
            raise ValueError(f"callback_info must be JSON serializable: {e}")

        payload = {"action": "custom", "callback_info": callback_info, "max_retries": max_retries, "task_id": task_id}
        from datetime import datetime, timedelta
        execute_time = datetime.now() + timedelta(seconds=delay_seconds)
        await container.task_repo.push(task_type="custom_task", payload=payload, priority=3, scheduled_at=execute_time)
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        try:
            async with container.db.get_session() as session:
                stmt = select(TaskQueue).where(TaskQueue.task_data.like(f"%{task_id}%"))
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                if not task: return None
                task_data = json.loads(task.task_data) if task.task_data else {}
                return {"task_id": task_data.get("task_id", task_id), "status": task.status, "task_type": task.task_type}
        except Exception as e:
            logger.error(f"[TaskService] get_task_status failed: {e}")
            return None

    async def get_active_tasks_count(self) -> int:
        """获取活跃任务数量"""
        try:
            async with container.db.get_session() as session:
                from sqlalchemy import func
                stmt = select(func.count(TaskQueue.id)).where(TaskQueue.status.in_(["pending", "running"]))
                result = await session.execute(stmt)
                return result.scalar_one()
        except Exception as e:
            logger.error(f"[TaskService] get_active_tasks_count failed: {e}")
            return 0

    async def shutdown(self):
        """关闭任务管理器"""
        logger.info("[TaskService] 消息任务管理服务已关闭")


    async def schedule_delete(
        self,
        message: Any = None,
        delay_seconds: float = 0,
        task_id: Optional[str] = None,
        max_retries: int = 3,
        chat_id: Optional[int] = None,
        message_ids: Optional[List[int]] = None
    ) -> str:
        """安排消息删除任务 - 持久化版本"""
        if delay_seconds == -1:
            return ""

        effective_chat_id = chat_id or (message.chat_id if message else None)
        effective_message_ids = message_ids or ([message.id] if message else [])

        if not effective_chat_id or not effective_message_ids:
            logger.warning("[TaskService] schedule_delete 失败: 缺少 chat_id 或 message_ids")
            return ""

        if task_id is None:
            import time
            task_id = f"delete_{effective_chat_id}_{time.time()}"

        payload = {
            "action": "delete",
            "chat_id": effective_chat_id,
            "message_ids": effective_message_ids,
            "max_retries": max_retries,
            "task_id": task_id,
        }

        from datetime import datetime, timedelta
        execute_time = datetime.now() + timedelta(seconds=delay_seconds)

        await container.task_repo.push(
            task_type="message_delete",
            payload=payload,
            priority=5,
            scheduled_at=execute_time,
        )

        logger.info(f"已安排持久化删除任务: {task_id}, 延迟: {delay_seconds}s")
        return task_id

    async def cancel_task(self, task_id: str) -> bool:
        """取消指定任务"""
        if not task_id:
            return False

        try:
            async with container.db.get_session() as session:
                from sqlalchemy import select
                from datetime import datetime
                
                stmt = select(TaskQueue).where(
                    TaskQueue.task_data.like(f"%{task_id}%"),
                    TaskQueue.status == "pending",
                )
                result = await session.execute(stmt)
                tasks = result.scalars().all()

                if not tasks:
                    return False

                for task in tasks:
                    task.status = "completed"
                    task.completed_at = datetime.utcnow()
                
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, 错误: {e}")
            return False

# 全局任务管理服务实例
task_service = TaskService()
# [Compatibility Alias]
message_task_manager = task_service


