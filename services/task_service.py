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
    async def list_tasks(self, task_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """列出最近的任务 (原生异步)
        
        Args:
            task_type: 任务类型，None表示所有类型
            limit: 返回的最大任务数量
            
        Returns:
            包含任务列表的字典
        """
        logger.info(f"[TaskService] 开始列出任务，类型={task_type}，限制={limit}")
        
        try:
            async with container.db.session() as session:
                stmt = (
                    select(TaskQueue)
                    .order_by(TaskQueue.id.desc())
                    .limit(limit)
                )
                
                # 根据task_type过滤
                if task_type:
                    stmt = stmt.filter(TaskQueue.task_type == task_type)
                    logger.debug(f"[TaskService] 根据类型过滤任务: {task_type}")
                    
                result = await session.execute(stmt)
                rows = result.scalars().all()
                
            tasks = []
            for r in rows:
                try:
                    data = json.loads(r.task_data) if r.task_data else {}
                except Exception as json_err:
                    logger.warning(f"[TaskService] 解析任务数据失败，ID={r.id}，错误={json_err}")
                    data = {}
                
                task_info = {
                    'id': r.id,
                    'status': r.status,
                    'started_at': r.started_at,
                    'completed_at': r.completed_at,
                    'forwarded': r.forwarded_count if r.forwarded_count is not None else data.get('forwarded', 0),
                    'filtered': r.filtered_count if r.filtered_count is not None else data.get('filtered', 0),
                    'failed': r.failed_count if r.failed_count is not None else data.get('failed', 0),
                    'total': r.total_count if r.total_count is not None else data.get('total', 0),
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
        """获取任务详情 (原生异步)
        
        Args:
            task_id: 任务ID，None表示获取最新任务
            task_type: 任务类型，None表示所有类型
            
        Returns:
            包含任务详情的字典
        """
        try:
            async with container.db.session() as session:
                if task_id is not None:
                    stmt = select(TaskQueue).filter(TaskQueue.id == task_id)
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                else:
                    stmt = (
                        select(TaskQueue)
                        .order_by(TaskQueue.id.desc())
                        .limit(1)
                    )
                    
                    # 根据task_type过滤
                    if task_type:
                        stmt = stmt.filter(TaskQueue.task_type == task_type)
                        
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
            
            if not row:
                return {'success': False, 'error': '未找到任务'}
            try:
                data = json.loads(row.task_data) if row.task_data else {}
            except Exception:
                data = {}
            detail = {
                'id': row.id,
                'status': row.status,
                'started_at': row.started_at,
                'completed_at': row.completed_at,
                'data': {
                    **data,
                    'done': getattr(row, 'done_count', data.get('done', 0)),
                    'total': getattr(row, 'total_count', data.get('total', 0)),
                    'forwarded': getattr(row, 'forwarded_count', data.get('forwarded', 0)),
                    'filtered': getattr(row, 'filtered_count', data.get('filtered', 0)),
                    'failed': getattr(row, 'failed_count', data.get('failed', 0)),
                    'last_id': getattr(row, 'last_message_id', data.get('last_id')),
                    'source_chat_id': getattr(row, 'source_chat_id', data.get('source_chat_id')),
                    'target_chat_id': getattr(row, 'target_chat_id', data.get('target_chat_id')),
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
        """获取最近任务的失败样本 (原生异步)
        
        Args:
            limit: 返回的最大失败样本数量
            task_type: 任务类型，默认history_forward
            
        Returns:
            包含失败样本的字典
        """
        try:
            async with container.db.session() as session:
                stmt = (
                    select(TaskQueue)
                    .order_by(TaskQueue.id.desc())
                    .limit(1)
                )
                
                # 根据task_type过滤
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
                except Exception:
                    pass
            return {'success': True, 'failed_ids': failed_ids}
        except Exception as e:
            logger.error(f"获取失败样本失败: {e}")
            return {'success': False, 'error': str(e), 'failed_ids': []}


task_service = TaskService()


