import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import update
from models.system import TaskQueue

logger = logging.getLogger(__name__)

class TaskStatusSink:
    """
    单例模式：全局唯一的任务状态内存缓冲池。
    CQRS 架构下，接受所有的状态更新指令，并以 batch 形式合并落盘。
    """
    _instance = None
    _queue: asyncio.Queue = None
    _batch_size: int = 500
    _flush_interval: float = 0.5
    _daemon_task: asyncio.Task = None
    _running: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskStatusSink, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
        
    def _init(self):
        self._queue = asyncio.Queue()
        self._running = False
        
    def start(self):
        if not self._running:
            self._running = True
            self._daemon_task = asyncio.create_task(self._daemon_loop(), name="task_status_sink_daemon")
            logger.info(f"🚀 TaskStatusSink 批处理缓冲池已启动 (Batch Size: {self._batch_size}, Interval: {self._flush_interval}s)")

    async def stop(self):
        if self._running:
            self._running = False
            logger.info("🛑 正在停止 TaskStatusSink 并排空缓冲池...")
            await self.flush()
            if self._daemon_task:
                self._daemon_task.cancel()
                try:
                    await self._daemon_task
                except asyncio.CancelledError:
                    pass

    async def put(self, task_id: int, action: str, error_message: str = None):
        """
        抛后即忘的方法。供高频 Worker 调用。
        action: 'complete' 或 'fail'
        """
        payload = {"id": task_id, "action": action, "error_message": error_message}
        await self._queue.put(payload)
        
    async def _daemon_loop(self):
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TaskStatusSink 守护进程异常: {e}", exc_info=True)
                await asyncio.sleep(1.0)
                
    async def flush(self):
        """将缓存的所有命令抽干并执行一次性 DB 批量写入"""
        if self._queue.empty():
            return
            
        items = []
        # 提取当前所有积压的请求
        while not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
                
        if not items:
            return
            
        asyncio.create_task(self._process_batch(items))
        
    async def _process_batch(self, items: List[Dict[str, Any]]):
        """统一执行 DB 写入，对完成和失败进行合并分类操作"""
        completed_ids = []
        failed_commands = []
        
        for item in items:
            action = item.get("action")
            task_id = item.get("id")
            
            if action == 'complete':
                completed_ids.append(task_id)
            elif action == 'fail':
                failed_commands.append(item)
                
        now = datetime.utcnow()
        # 1. 批量处理 Completed (聚合 IN 操作，极高效率)
        total_affected = 0
        from core.db_factory import AsyncSessionManager

        try:
            async with AsyncSessionManager() as session:
                if completed_ids:
                    # 批量切割以防 IN 语句过长 (SQLite 有限制)
                    chunk_size = 999
                    for i in range(0, len(completed_ids), chunk_size):
                        chunk = completed_ids[i:i + chunk_size]
                        result = await session.execute(
                            update(TaskQueue)
                            .where(TaskQueue.id.in_(chunk))
                            .where(TaskQueue.status.in_(['running', 'pending']))
                            .values(status='completed', completed_at=now, updated_at=now)
                        )
                        total_affected += result.rowcount
                        
                # 2. 批量处理 Failed (由于附带不同的 error_message，虽然批量但是各自 UPDATE 比较安全，仍在同一事务内)
                # 使用 executemany 的隐式支持（SQLAlchemy 2.0+支持字典列表绑定）
                if failed_commands:
                    update_params = [
                        {"b_id": cmd["id"], "b_err": str(cmd["error_message"])}
                        for cmd in failed_commands
                    ]
                    # 我们用独立循环，因为 SQLAlchemy 报错时，整批会失败。其实单独执行速度在一个事务里也很快。
                    for params in update_params:
                         result = await session.execute(
                             update(TaskQueue)
                             .where(TaskQueue.id == params["b_id"])
                             .where(TaskQueue.status.in_(['running', 'pending']))
                             .values(status='failed', error_message=params["b_err"], updated_at=now)
                         )
                         total_affected += result.rowcount
                
                await session.commit()
                if total_affected > 0:
                    logger.debug(f"[BatchSink] 批量消费任务状态完成: 提交 {len(items)} 条, 成功更新 {total_affected} 行")
                    
        except Exception as e:
            logger.error(f"[BatchSink] 批量写入状态失败，尝试重入队列 ({len(items)} 条): {e}")
            # 带 retry_count 重入队列，避免静默丢失数据
            MAX_RETRY = 3
            requeued, dropped = 0, 0
            for item in items:
                retry_count = item.get("_retry", 0)
                if retry_count < MAX_RETRY:
                    item["_retry"] = retry_count + 1
                    await self._queue.put(item)
                    requeued += 1
                else:
                    logger.warning(
                        f"[BatchSink] 任务 {item.get('id')} 重试超 {MAX_RETRY} 次，永久丢弃"
                    )
                    dropped += 1
            if requeued:
                logger.info(f"[BatchSink] 已重入队列 {requeued} 条，丢弃 {dropped} 条")

# 初始化暴露实例
task_status_sink = TaskStatusSink()
