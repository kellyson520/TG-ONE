import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import bindparam, or_, update
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
        self._flush_event = asyncio.Event()
        self._processing_tasks = set()
        self._flush_lock = asyncio.Lock()
        self._process_lock = asyncio.Lock()
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._daemon_task = asyncio.create_task(
                self._daemon_loop(),
                name="task_status_sink_daemon",
            )
            if not self._queue.empty():
                self._notify_work()
            logger.info(
                "🚀 TaskStatusSink 批处理缓冲池已启动 "
                f"(Batch Size: {self._batch_size}, "
                f"Interval: {self._flush_interval}s)"
            )

    @property
    def running(self) -> bool:
        return self._running

    async def stop(self):
        if self._running:
            self._running = False
            logger.info("🛑 正在停止 TaskStatusSink 并排空缓冲池...")
            if self._daemon_task:
                self._daemon_task.cancel()
                try:
                    await self._daemon_task
                except asyncio.CancelledError:
                    logger.debug("TaskStatusSink 守护任务已取消")
            await self.flush(wait=True)
            if self._processing_tasks:
                await asyncio.gather(
                    *list(self._processing_tasks),
                    return_exceptions=True,
                )

    async def put(
        self,
        task_id: int,
        action: str,
        error_message: str = None,
    ):
        """
        抛后即忘的方法。供高频 Worker 调用。
        action: 'complete' 或 'fail'
        """
        payload = {
            "id": task_id,
            "action": action,
            "error_message": error_message,
        }
        await self._queue.put(payload)
        self._notify_work()

    def _notify_work(self):
        if self._running:
            self._flush_event.set()

    async def _daemon_loop(self):
        while self._running:
            try:
                await self._wait_for_flush_window()
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TaskStatusSink 守护进程异常: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _wait_for_flush_window(self):
        if self._queue.empty():
            self._flush_event.clear()
            if self._queue.empty():
                await self._flush_event.wait()

        deadline = asyncio.get_running_loop().time() + self._flush_interval
        while self._running and not self._queue.empty():
            if self._queue.qsize() >= self._batch_size:
                break

            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break

            self._flush_event.clear()
            try:
                await asyncio.wait_for(
                    self._flush_event.wait(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                break

    async def flush(self, wait: bool = False):
        """将缓存的所有命令抽干并执行一次性 DB 批量写入"""
        async with self._flush_lock:
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

        task = asyncio.create_task(
            self._process_batch(items),
            name="task_status_sink_process_batch",
        )
        self._processing_tasks.add(task)
        task.add_done_callback(self._processing_tasks.discard)
        if wait:
            await task

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
            async with self._process_lock:
                async with AsyncSessionManager() as session:
                    if completed_ids:
                        # 批量切割以防 IN 语句过长 (SQLite 有限制)
                        chunk_size = 999
                        for i in range(0, len(completed_ids), chunk_size):
                            chunk = completed_ids[i:i + chunk_size]
                            result = await session.execute(
                                update(TaskQueue)
                                .where(TaskQueue.id.in_(chunk))
                                .where(
                                    TaskQueue.status.in_(
                                        ['running', 'pending']
                                    )
                                )
                                .values(
                                    status='completed',
                                    completed_at=now,
                                    updated_at=now,
                                )
                            )
                            total_affected += result.rowcount

                    # 2. 批量处理 Failed。
                    # 各条 error_message 不同，逐条 UPDATE 但仍复用同一事务。
                    if failed_commands:
                        update_params = [
                            {
                                "b_id": cmd["id"],
                                "b_err": str(cmd["error_message"]),
                                "b_status": 'failed',
                                "b_now": now,
                            }
                            for cmd in failed_commands
                        ]
                        # [FIX] 原来是「每条一次 execute」：一批最多 500 条失败，
                        # 等于同一事务里 500 次往返，长写事务会把 WAL 和连接池一起拖住
                        # （审查 #9）。改成 executemany，一条语句带一组参数。
                        # 走 Core 表对象：ORM 实体 + 参数列表会走「按主键批量更新」，
                        # 要求每个 dict 带 PK，否则报 No primary key value supplied。
                        _t = TaskQueue.__table__
                        result = await session.execute(
                            _t.update()
                            .where(_t.c.id == bindparam("b_id"))
                            # IN (...) 会生成 expanding 参数，和 executemany 冲突
                            # （InvalidRequestError: 'expanding' not supported）。
                            # 拆成两个等值条件的 OR，executemany 就能走。
                            .where(or_(_t.c.status == 'running', _t.c.status == 'pending'))
                            # 全部走 bindparam：executemany 下不允许混入字面量
                            # （否则 SQLAlchemy 要求 literal_execute，直接 InvalidRequestError）
                            .values(
                                status=bindparam("b_status"),
                                error_message=bindparam("b_err"),
                                updated_at=bindparam("b_now"),
                            ),
                            update_params,
                        )
                        total_affected += result.rowcount or 0

                    await session.commit()
                    if total_affected > 0:
                        logger.debug(
                            "[BatchSink] 批量消费任务状态完成: "
                            f"提交 {len(items)} 条, "
                            f"成功更新 {total_affected} 行"
                        )

        except Exception as e:
            logger.error(
                "[BatchSink] 批量写入状态失败，尝试重入队列 "
                f"({len(items)} 条): {e}"
            )
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
                        f"[BatchSink] 任务 {item.get('id')} "
                        f"重试超 {MAX_RETRY} 次，永久丢弃"
                    )
                    dropped += 1
            if requeued:
                logger.info(
                    f"[BatchSink] 已重入队列 {requeued} 条，"
                    f"丢弃 {dropped} 条"
                )
                self._notify_work()


# 初始化暴露实例
task_status_sink = TaskStatusSink()
