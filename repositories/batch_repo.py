"""
批量处理器和异步数据库操作优化
提供高效的批量操作、异步处理、连接池管理等功能
"""

import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

import asyncio
import time
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Union

from models.models import get_dedup_session, get_read_session, get_session
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BatchOperation:
    """批量操作任务"""

    operation_id: str
    operation_type: str  # 'insert', 'update', 'delete'
    table_name: str
    data: List[Dict[str, Any]]
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class BatchResult:
    """批量操作结果"""

    operation_id: str
    success: bool
    processed_count: int
    error_count: int
    duration: float
    errors: List[str] = field(default_factory=list)


# WARNING: DO NOT USE FOR CRITICAL DATA (e.g. TASKS, BILLING). DATA MAY BE LOST ON CRASH.
# 这是一个典型的"Write-Behind"（写后）缓存。虽然提高了吞吐量，但如果在 Flush 之前系统崩溃，数据会丢失。
# 绝对禁止在 UserMessageHandler (消息接收) 和 TaskRepository (关键状态变更) 中使用 BatchProcessor。
# 允许使用于 ChatStatistics、RuleStatistics 等丢几条数据无伤大雅的统计业务。
class AsyncBatchProcessor:
    """异步批量处理器"""

    def __init__(
        self,
        max_batch_size: int = 1000,
        batch_timeout: float = 5.0,
        max_workers: int = 4,
    ):
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.max_workers = max_workers

        self.pending_operations = deque()
        self.processing_queue = asyncio.Queue()
        self.results = {}

        self.is_running = False
        self.worker_tasks = []
        self.batch_timer_task = None

        # 新增结果过期时间 (秒)
        self.result_ttl = 300

        self.lock = asyncio.Lock()
        self.stats = {
            "total_processed": 0,
            "total_errors": 0,
            "avg_batch_size": 0,
            "avg_processing_time": 0,
        }

    async def start(self):
        """启动批量处理器"""
        if self.is_running:
            return

        self.is_running = True

        # 启动工作协程
        for i in range(self.max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(task)

        # 启动批量计时器
        self.batch_timer_task = asyncio.create_task(self._batch_timer())

        logger.info(f"AsyncBatchProcessor started with {self.max_workers} workers")

    async def stop(self):
        """停止批量处理器"""
        if not self.is_running:
            return

        self.is_running = False

        # 处理剩余操作
        await self._flush_pending_operations()

        # 停止工作协程
        for task in self.worker_tasks:
            task.cancel()

        if self.batch_timer_task:
            self.batch_timer_task.cancel()

        await asyncio.gather(
            *self.worker_tasks, self.batch_timer_task, return_exceptions=True
        )

        logger.info("AsyncBatchProcessor stopped")

    async def submit_operation(
        self,
        operation_type: str,
        table_name: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        priority: int = 0,
    ) -> str:
        """提交批量操作"""
        if not self.is_running:
            await self.start()

        operation_id = str(uuid.uuid4())

        # 确保data是列表
        if isinstance(data, dict):
            data = [data]

        operation = BatchOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            table_name=table_name,
            data=data,
            priority=priority,
        )

        async with self.lock:
            self.pending_operations.append(operation)

        return operation_id

    async def get_result(
        self, operation_id: str, timeout: float = 30.0
    ) -> Optional[BatchResult]:
        """获取操作结果"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if operation_id in self.results:
                # 解包元组
                data = self.results.pop(operation_id)
                if isinstance(data, tuple):
                    return data[1]
                return data

            await asyncio.sleep(0.1)

        return None

    async def _worker(self, worker_name: str):
        """工作协程"""
        logger.debug(f"Batch worker {worker_name} started")

        while self.is_running:
            try:
                # 从队列获取批量操作
                operations = await self._get_batch_from_queue()

                if operations:
                    await self._process_batch(operations, worker_name)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch worker {worker_name} error: {e}")
                await asyncio.sleep(1)

        logger.debug(f"Batch worker {worker_name} stopped")

    async def _batch_timer(self):
        """批量计时器 + 结果清理"""
        while self.is_running:
            try:
                await asyncio.sleep(self.batch_timeout)
                await self._flush_pending_operations()
                # 新增：清理过期结果
                self._cleanup_stale_results()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch timer error: {e}")

    def _cleanup_stale_results(self):
        """清理未被领取的过期结果"""
        now = time.time()
        expired_ids = []

        for op_id, data in list(self.results.items()):
            # 兼容处理：检查data是否是元组
            if isinstance(data, tuple) and len(data) == 2:
                ts, _ = data
                if now - ts > self.result_ttl:
                    expired_ids.append(op_id)
            # 如果是旧格式直接存储的Result对象，强制清理
            elif isinstance(data, BatchResult):
                # 假设旧对象存活时间较短，直接保留或根据策略清理
                pass

        for op_id in expired_ids:
            self.results.pop(op_id, None)

        if expired_ids:
            logger.debug(f"清理了 {len(expired_ids)} 个过期批量结果")

    async def _flush_pending_operations(self):
        """刷新待处理操作"""
        async with self.lock:
            if self.pending_operations:
                operations = list(self.pending_operations)
                self.pending_operations.clear()

                # 按表和操作类型分组
                grouped = self._group_operations(operations)

                for group in grouped:
                    await self.processing_queue.put(group)

    def _group_operations(
        self, operations: List[BatchOperation]
    ) -> List[List[BatchOperation]]:
        """将操作按表和类型分组"""
        groups = defaultdict(list)

        for op in operations:
            key = (op.table_name, op.operation_type)
            groups[key].append(op)

        # 按优先级排序每个组
        for key in groups:
            groups[key].sort(key=lambda x: x.priority, reverse=True)

        return list(groups.values())

    async def _get_batch_from_queue(self) -> Optional[List[BatchOperation]]:
        """从队列获取批量操作"""
        try:
            return await asyncio.wait_for(self.processing_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def _process_batch(self, operations: List[BatchOperation], worker_name: str):
        """处理批量操作"""
        if not operations:
            return

        start_time = time.time()
        table_name = operations[0].table_name
        operation_type = operations[0].operation_type

        logger.debug(
            f"Worker {worker_name} processing {len(operations)} {operation_type} operations for {table_name}"
        )

        try:
            if operation_type == "insert":
                results = await self._batch_insert(operations)
            elif operation_type == "update":
                results = await self._batch_update(operations)
            elif operation_type == "delete":
                results = await self._batch_delete(operations)
            else:
                logger.error(f"Unknown operation type: {operation_type}")
                return

            duration = time.time() - start_time

            # 更新统计
            self.stats["total_processed"] += len(operations)

            # 存储结果时带上时间戳
            current_ts = time.time()
            for op, result in zip(operations, results):
                self.results[op.operation_id] = (current_ts, result)

            logger.debug(f"Batch processing completed in {duration:.3f}s")

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")

            # 创建错误结果，带时间戳
            current_ts = time.time()
            for op in operations:
                error_result = BatchResult(
                    operation_id=op.operation_id,
                    success=False,
                    processed_count=0,
                    error_count=len(op.data),
                    duration=time.time() - start_time,
                    errors=[str(e)],
                )
                self.results[op.operation_id] = (current_ts, error_result)

    async def _batch_insert(
        self, operations: List[BatchOperation]
    ) -> List[BatchResult]:
        """批量插入"""
        results = []

        for operation in operations:
            start_time = time.time()
            processed_count = 0
            error_count = 0
            errors = []

            try:
                # 分批处理大量数据
                for chunk in self._chunk_data(operation.data, self.max_batch_size):
                    try:
                        await self._execute_batch_insert(operation.table_name, chunk)
                        processed_count += len(chunk)
                    except Exception as e:
                        error_count += len(chunk)
                        errors.append(str(e))

                result = BatchResult(
                    operation_id=operation.operation_id,
                    success=error_count == 0,
                    processed_count=processed_count,
                    error_count=error_count,
                    duration=time.time() - start_time,
                    errors=errors,
                )

            except Exception as e:
                result = BatchResult(
                    operation_id=operation.operation_id,
                    success=False,
                    processed_count=0,
                    error_count=len(operation.data),
                    duration=time.time() - start_time,
                    errors=[str(e)],
                )

            results.append(result)

        return results

    async def _batch_update(
        self, operations: List[BatchOperation]
    ) -> List[BatchResult]:
        """批量更新"""
        results = []

        for operation in operations:
            start_time = time.time()
            processed_count = 0
            error_count = 0
            errors = []

            try:
                for item in operation.data:
                    try:
                        await self._execute_single_update(operation.table_name, item)
                        processed_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(str(e))

                result = BatchResult(
                    operation_id=operation.operation_id,
                    success=error_count == 0,
                    processed_count=processed_count,
                    error_count=error_count,
                    duration=time.time() - start_time,
                    errors=errors,
                )

            except Exception as e:
                result = BatchResult(
                    operation_id=operation.operation_id,
                    success=False,
                    processed_count=0,
                    error_count=len(operation.data),
                    duration=time.time() - start_time,
                    errors=[str(e)],
                )

            results.append(result)

        return results

    async def _batch_delete(
        self, operations: List[BatchOperation]
    ) -> List[BatchResult]:
        """批量删除"""
        results = []

        for operation in operations:
            start_time = time.time()
            processed_count = 0
            error_count = 0
            errors = []

            try:
                # 收集所有ID
                ids = []
                for item in operation.data:
                    if "id" in item:
                        ids.append(item["id"])

                if ids:
                    try:
                        await self._execute_batch_delete(operation.table_name, ids)
                        processed_count = len(ids)
                    except Exception as e:
                        error_count = len(ids)
                        errors.append(str(e))

                result = BatchResult(
                    operation_id=operation.operation_id,
                    success=error_count == 0,
                    processed_count=processed_count,
                    error_count=error_count,
                    duration=time.time() - start_time,
                    errors=errors,
                )

            except Exception as e:
                result = BatchResult(
                    operation_id=operation.operation_id,
                    success=False,
                    processed_count=0,
                    error_count=len(operation.data),
                    duration=time.time() - start_time,
                    errors=[str(e)],
                )

            results.append(result)

        return results

    def _chunk_data(
        self, data: List[Dict[str, Any]], chunk_size: int
    ) -> List[List[Dict[str, Any]]]:
        """将数据分块"""
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    async def _execute_batch_insert(self, table_name: str, data: List[Dict[str, Any]]):
        """执行批量插入"""
        if not data:
            return

        def _insert_batch(session: Session):
            if table_name == "media_signatures":
                from models.models import MediaSignature

                objects = [MediaSignature(**item) for item in data]
                session.add_all(objects)

            elif table_name == "keywords":
                from models.models import Keyword

                objects = [Keyword(**item) for item in data]
                session.add_all(objects)

            elif table_name == "error_logs":
                from models.models import ErrorLog

                objects = [ErrorLog(**item) for item in data]
                session.add_all(objects)

            else:
                # 通用插入（使用原生SQL）
                if data:
                    columns = list(data[0].keys())
                    placeholders = ", ".join([f":{col}" for col in columns])
                    columns_str = ", ".join(columns)

                    sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                    session.execute(text(sql), data)

            session.commit()

        # 在线程池中执行数据库操作
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            if table_name == "media_signatures":
                await loop.run_in_executor(
                    executor, lambda: self._run_with_dedup_session(_insert_batch)
                )
            else:
                await loop.run_in_executor(
                    executor, lambda: self._run_with_session(_insert_batch)
                )

    async def _execute_single_update(self, table_name: str, data: Dict[str, Any]):
        """执行单个更新"""

        def _update_item(session: Session):
            if "id" not in data:
                raise ValueError("Update data must contain 'id' field")

            item_id = data["id"]
            update_data = {k: v for k, v in data.items() if k != "id"}

            if update_data:
                set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
                sql = f"UPDATE {table_name} SET {set_clause} WHERE id = :id"

                params = {**update_data, "id": item_id}
                session.execute(text(sql), params)
                session.commit()

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(
                executor, lambda: self._run_with_session(_update_item)
            )

    async def _execute_batch_delete(self, table_name: str, ids: List[int]):
        """执行批量删除"""

        def _delete_batch(session: Session):
            if len(ids) == 1:
                sql = f"DELETE FROM {table_name} WHERE id = :id"
                session.execute(text(sql), {"id": ids[0]})
            else:
                # 使用IN子句
                placeholders = ", ".join([f":id_{i}" for i in range(len(ids))])
                sql = f"DELETE FROM {table_name} WHERE id IN ({placeholders})"

                params = {f"id_{i}": id_val for i, id_val in enumerate(ids)}
                session.execute(text(sql), params)

            session.commit()

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(
                executor, lambda: self._run_with_session(_delete_batch)
            )

    def _run_with_session(self, func: Callable[[Session], None]):
        """在会话中运行函数"""
        with get_session() as session:
            func(session)

    def _run_with_dedup_session(self, func: Callable[[Session], None]):
        with get_dedup_session() as session:
            func(session)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "is_running": self.is_running,
            "pending_operations": len(self.pending_operations),
            "active_workers": len(self.worker_tasks),
            "stats": self.stats.copy(),
        }


class ConnectionPoolManager:
    """连接池管理器"""

    def __init__(self):
        self.read_pool_stats = {"active": 0, "idle": 0}
        self.write_pool_stats = {"active": 0, "idle": 0}

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        try:
            from models.models import get_engine

            engine = get_engine()
            pool = engine.pool

            status = {
                "pool_size": pool.size() if hasattr(pool, "size") else "unknown",
                "checked_in": (
                    pool.checkedin() if hasattr(pool, "checkedin") else "unknown"
                ),
                "checked_out": (
                    pool.checkedout() if hasattr(pool, "checkedout") else "unknown"
                ),
                "overflow": pool.overflow() if hasattr(pool, "overflow") else "unknown",
                "invalid": pool.invalid() if hasattr(pool, "invalid") else "unknown",
            }

            return status

        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {"error": str(e)}

    @asynccontextmanager
    async def get_optimized_session(self, read_only: bool = False):
        """获取优化的数据库会话"""
        session_func = get_read_session if read_only else get_session

        start_time = time.time()
        try:
            with session_func() as session:
                yield session
        finally:
            duration = time.time() - start_time
            logger.debug(f"Session duration: {duration:.3f}s (read_only={read_only})")


class AsyncQueryExecutor:
    """异步查询执行器"""

    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)

    async def execute_query(self, query_func: Callable, *args, **kwargs) -> Any:
        """异步执行查询"""
        async with self.semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self.executor, query_func, *args, **kwargs
            )

    async def execute_multiple_queries(
        self, queries: List[Tuple[Callable, tuple, dict]]
    ) -> List[Any]:
        """并发执行多个查询"""
        tasks = []

        for query_func, args, kwargs in queries:
            task = self.execute_query(query_func, *args, **kwargs)
            tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)

    def shutdown(self):
        """关闭执行器"""
        self.executor.shutdown(wait=True)


# 全局实例
batch_processor = AsyncBatchProcessor()
connection_manager = ConnectionPoolManager()
query_executor = AsyncQueryExecutor()


# 便捷函数
async def batch_insert(
    table_name: str, data: List[Dict[str, Any]], priority: int = 0
) -> str:
    """批量插入数据"""
    return await batch_repo.submit_operation("insert", table_name, data, priority)


async def batch_update(
    table_name: str, data: List[Dict[str, Any]], priority: int = 0
) -> str:
    """批量更新数据"""
    return await batch_repo.submit_operation("update", table_name, data, priority)


async def batch_delete(
    table_name: str, data: List[Dict[str, Any]], priority: int = 0
) -> str:
    """批量删除数据"""
    return await batch_repo.submit_operation("delete", table_name, data, priority)


async def wait_for_operation(
    operation_id: str, timeout: float = 30.0
) -> Optional[BatchResult]:
    """等待操作完成"""
    return await batch_repo.get_result(operation_id, timeout)


def get_batch_processor_stats() -> Dict[str, Any]:
    """获取批量处理器统计"""
    return batch_repo.get_stats()


def get_connection_pool_status() -> Dict[str, Any]:
    """获取连接池状态"""
    return connection_manager.get_pool_status()


async def start_batch_processing():
    """启动批量处理服务"""
    await batch_repo.start()
    logger.info("Batch processing services started")


async def stop_batch_processing():
    """停止批量处理服务"""
    await batch_repo.stop()
    query_executor.shutdown()
    logger.info("Batch processing services stopped")


# 使用示例和装饰器
def batched_operation(batch_size: int = 100):
    """批量操作装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 这里可以实现自动批量化逻辑
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def optimize_large_query(
    query_func: Callable, chunk_size: int = 1000
) -> AsyncGenerator[Any, None]:
    """优化大查询，分块返回结果"""
    offset = 0

    while True:
        chunk_results = await query_executor.execute_query(
            query_func, limit=chunk_size, offset=offset
        )

        if not chunk_results:
            break

        for result in chunk_results:
            yield result

        if len(chunk_results) < chunk_size:
            break

        offset += chunk_size
