"""
统一的消息任务管理器
解决消息撤回延迟和任务管理问题
使用 TaskQueue 持久化存储，符合 S7 架构标准
"""

from datetime import datetime, timedelta

import logging
import time
from typing import Any, Callable, Dict, Optional

from core.container import container

logger = logging.getLogger(__name__)


class MessageTaskManager:
    """统一的消息任务管理器 - 使用 TaskQueue 持久化存储"""

    def __init__(self):
        # 不需要内存存储，所有任务都持久化到数据库
        self._db = container.db
        self._task_repo = container.task_repo

    async def schedule_delete(
        self,
        message: Any,
        delay_seconds: float,
        task_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """安排消息删除任务 - 持久化版本

        Args:
            message: 要删除的消息对象
            delay_seconds: 延迟秒数，0表示立即删除，-1表示不删除
            task_id: 可选的任务ID，如果不提供则自动生成
            max_retries: 最大重试次数

        Returns:
            任务ID字符串
        """
        if delay_seconds == -1:
            return ""  # 不删除

        # 生成任务ID
        if task_id is None:
            task_id = f"delete_{id(message)}_{time.time()}"

        # 构建任务数据
        payload = {
            "action": "delete",
            "chat_id": message.chat_id,
            "message_ids": [message.id],
            "max_retries": max_retries,
            "task_id": task_id,
        }

        # 计算执行时间
        execute_time = datetime.now() + timedelta(seconds=delay_seconds)

        # 写入 TaskQueue
        await self._task_repo.push(
            task_type="message_delete",
            payload=payload,
            priority=5,  # 删除任务优先级较高
            scheduled_at=execute_time,
        )

        logger.info(
            f"已安排持久化删除任务: {task_id}, 延迟: {delay_seconds}s, 执行时间: {execute_time}"
        )
        return task_id

    async def schedule_custom_task(
        self,
        callback_info: Dict,
        delay_seconds: float,
        task_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """安排自定义任务 - 持久化版本

        Args:
            callback_info: 回调函数信息，包含模块路径和函数名
            delay_seconds: 延迟秒数
            task_id: 可选的任务ID
            max_retries: 最大重试次数

        Returns:
            任务ID
        """
        if not callback_info or not isinstance(callback_info, dict):
            logger.error("自定义任务回调信息无效")
            return ""

        # 生成任务ID
        if task_id is None:
            task_id = f"custom_{time.time()}_{id(callback_info)}"

        # 构建任务数据
        payload = {
            "action": "custom",
            "callback_info": callback_info,
            "max_retries": max_retries,
            "task_id": task_id,
        }

        # 计算执行时间
        execute_time = datetime.now() + timedelta(seconds=delay_seconds)

        # 写入 TaskQueue
        await self._task_repo.push(
            task_type="custom_task",
            payload=payload,
            priority=3,  # 自定义任务优先级中等
            scheduled_at=execute_time,
        )

        logger.info(
            f"已安排持久化自定义任务: {task_id}, 延迟: {delay_seconds}s, 执行时间: {execute_time}"
        )
        return task_id

    async def cancel_task(self, task_id: str) -> bool:
        """取消指定任务

        Args:
            task_id: 要取消的任务ID

        Returns:
            取消是否成功
        """
        if not task_id:
            return False

        try:
            # 查询并取消任务
            async with self._db.session() as session:
                from sqlalchemy import select

                from models.models import TaskQueue

                # 查找匹配的任务
                stmt = select(TaskQueue).where(
                    TaskQueue.task_data.like(f"%{task_id}%"),
                    TaskQueue.status == "pending",
                )
                result = await session.execute(stmt)
                tasks = result.scalars().all()

                if not tasks:
                    logger.info(f"未找到待取消的任务: {task_id}")
                    return False

                # 将任务标记为已取消
                for task in tasks:
                    task.status = "completed"  # 使用completed状态表示已取消
                    task.completed_at = datetime.utcnow().isoformat()
                    task.updated_at = datetime.utcnow().isoformat()
                    logger.info(f"已取消任务: {task_id} (数据库ID: {task.id})")

                await session.commit()
                return True
        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, 错误: {str(e)}")
            return False

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态

        Args:
            task_id: 要查询的任务ID

        Returns:
            任务状态信息
        """
        if not task_id:
            return None

        try:
            async with self._db.session() as session:
                import json
                from sqlalchemy import select

                from models.models import TaskQueue

                # 查找匹配的任务
                stmt = select(TaskQueue).where(TaskQueue.task_data.like(f"%{task_id}%"))
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if not task:
                    return None

                # 解析任务数据
                task_data = json.loads(task.task_data) if task.task_data else {}

                return {
                    "task_id": task_data.get("task_id", task_id),
                    "database_id": task.id,
                    "status": task.status,
                    "task_type": task.task_type,
                    "priority": task.priority,
                    "retry_count": task.retry_count,
                    "max_retries": task.max_retries,
                    "scheduled_at": task.scheduled_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "error_message": task.error_message,
                }
        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id}, 错误: {str(e)}")
            return None

    async def get_active_tasks_count(self) -> int:
        """获取活跃任务数量

        Returns:
            活跃任务数量
        """
        try:
            async with self._db.session() as session:
                from sqlalchemy import func, select

                from models.models import TaskQueue

                # 统计pending和running状态的任务数量
                stmt = select(func.count(TaskQueue.id)).where(
                    TaskQueue.status.in_(["pending", "running"])
                )
                result = await session.execute(stmt)
                count = result.scalar_one()

                logger.info(f"活跃任务数量: {count}")
                return count
        except Exception as e:
            logger.error(f"获取活跃任务数量失败: {str(e)}")
            return 0

    async def get_all_tasks_status(self) -> Dict:
        """获取所有任务状态统计

        Returns:
            任务状态统计信息
        """
        try:
            async with self._db.session() as session:
                from sqlalchemy import func, select

                from models.models import TaskQueue

                # 统计所有状态的任务数量
                stmt = select(
                    TaskQueue.status, func.count(TaskQueue.id).label("count")
                ).group_by(TaskQueue.status)
                result = await session.execute(stmt)
                status_counts = result.all()

                # 统计总任务数
                total_stmt = select(func.count(TaskQueue.id))
                total_result = await session.execute(total_stmt)
                total = total_result.scalar_one()

                # 构建统计结果
                status_dict = {status: count for status, count in status_counts}

                # 获取所有任务的简要信息
                tasks_stmt = (
                    select(TaskQueue).order_by(TaskQueue.created_at.desc()).limit(50)
                )
                tasks_result = await session.execute(tasks_stmt)
                tasks = tasks_result.scalars().all()

                tasks_info = {}
                import json

                for task in tasks:
                    task_data = json.loads(task.task_data) if task.task_data else {}
                    tasks_info[str(task.id)] = {
                        "task_id": task_data.get("task_id", f"task_{task.id}"),
                        "status": task.status,
                        "task_type": task.task_type,
                        "priority": task.priority,
                        "scheduled_at": task.scheduled_at,
                        "created_at": task.created_at,
                    }

                return {
                    "total": total,
                    "active": status_dict.get("pending", 0)
                    + status_dict.get("running", 0),
                    "completed": status_dict.get("completed", 0),
                    "failed": status_dict.get("failed", 0),
                    "status_counts": status_dict,
                    "recent_tasks": tasks_info,
                }
        except Exception as e:
            logger.error(f"获取所有任务状态失败: {str(e)}")
            return {
                "total": 0,
                "active": 0,
                "completed": 0,
                "failed": 0,
                "status_counts": {},
                "recent_tasks": {},
            }

    async def shutdown(self):
        """关闭任务管理器"""
        logger.info("消息任务管理器已关闭 (持久化任务不受影响)")
        # 不需要取消内存任务，因为所有任务都已持久化


# 全局任务管理器实例
message_task_manager = MessageTaskManager()
