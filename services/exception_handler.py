"""
全局异常处理器 (Global Exception Handler)

提供统一的异常捕捉、聚合和记录功能:
- 捕捉未处理的异步任务异常
- 异常聚合 (相同异常 10 分钟内只记录一次)
- 集成审计日志记录
- 支持异常回调钩子

创建于: 2026-01-11
Phase G.2: 全局异常捕捉
"""
import asyncio
import logging
import traceback
import hashlib
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional, Any, List
from collections import defaultdict
from functools import wraps

logger = logging.getLogger(__name__)


class ExceptionAggregate:
    """异常聚合记录"""
    __slots__ = ('exception_hash', 'first_occurrence', 'last_occurrence', 'count', 'sample_traceback')
    
    def __init__(self, exception_hash: str, traceback_str: str):
        self.exception_hash = exception_hash
        self.first_occurrence = datetime.utcnow()
        self.last_occurrence = datetime.utcnow()
        self.count = 1
        self.sample_traceback = traceback_str
    
    def increment(self):
        self.last_occurrence = datetime.utcnow()
        self.count += 1


class GlobalExceptionHandler:
    """
    全局异常处理器
    
    功能:
    1. 包装 asyncio.create_task 自动捕捉异常
    2. 异常聚合 (防止日志风暴)
    3. 可配置的异常回调钩子
    4. 集成审计日志记录
    
    使用:
        from services.exception_handler import exception_handler
        
        # 创建带异常捕捉的任务
        exception_handler.create_task(my_coroutine(), name="my_task")
        
        # 注册异常回调
        exception_handler.add_callback(my_error_handler)
    """
    
    # 异常聚合窗口 (10 分钟内相同异常只记录一次)
    AGGREGATION_WINDOW = timedelta(minutes=10)
    
    def __init__(self):
        self._aggregates: Dict[str, ExceptionAggregate] = {}
        self._callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def start(self):
        """启动异常处理器 (启动清理任务)"""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("GlobalExceptionHandler started")
    
    def stop(self):
        """停止异常处理器"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
        logger.info("GlobalExceptionHandler stopped")
    
    async def _cleanup_loop(self):
        """定期清理过期的异常聚合记录"""
        while self._running:
            try:
                await asyncio.sleep(300)  # 每 5 分钟清理一次
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception handler cleanup error: {e}")
    
    async def _cleanup_expired(self):
        """清理过期的异常聚合记录"""
        async with self._lock:
            now = datetime.utcnow()
            expired_keys = []
            for key, agg in self._aggregates.items():
                if now - agg.last_occurrence > self.AGGREGATION_WINDOW * 2:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._aggregates[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired exception aggregates")
    
    def _compute_exception_hash(self, exc: Exception) -> str:
        """计算异常的唯一标识 (基于类型和消息)"""
        exc_type = type(exc).__name__
        exc_msg = str(exc)[:200]  # 截断过长消息
        content = f"{exc_type}:{exc_msg}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def handle_exception(
        self,
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
        task_name: Optional[str] = None
    ) -> bool:
        """
        处理异常
        
        Args:
            exc: 异常对象
            context: 上下文信息
            task_name: 任务名称
            
        Returns:
            True 如果异常被记录 (非聚合), False 如果被聚合
        """
        exc_hash = self._compute_exception_hash(exc)
        tb_str = traceback.format_exc()
        
        async with self._lock:
            if exc_hash in self._aggregates:
                agg = self._aggregates[exc_hash]
                if datetime.utcnow() - agg.first_occurrence < self.AGGREGATION_WINDOW:
                    # 在聚合窗口内，只增加计数
                    agg.increment()
                    if agg.count == 5:
                        # 达到阈值时警告
                        logger.warning(
                            f"Exception aggregated ({agg.count}x in {self.AGGREGATION_WINDOW}): "
                            f"{type(exc).__name__}: {str(exc)[:100]}"
                        )
                    return False
                else:
                    # 窗口过期，重新开始
                    self._aggregates[exc_hash] = ExceptionAggregate(exc_hash, tb_str)
            else:
                # 新异常
                self._aggregates[exc_hash] = ExceptionAggregate(exc_hash, tb_str)
        
        # 记录异常
        await self._log_exception(exc, tb_str, context, task_name)
        
        # 调用回调
        await self._invoke_callbacks(exc, context, task_name)
        
        return True
    
    async def _log_exception(
        self,
        exc: Exception,
        tb_str: str,
        context: Optional[Dict],
        task_name: Optional[str]
    ):
        """记录异常到日志和审计系统"""
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        
        # 标准日志
        logger.error(
            f"Unhandled exception in {task_name or 'unknown task'}: {exc_type}: {exc_msg}",
            exc_info=False
        )
        logger.debug(f"Traceback:\n{tb_str}")
        
        # 审计日志
        try:
            from services.audit_service import audit_service
            await audit_service.log_event(
                action="UNHANDLED_EXCEPTION",
                resource_type="SYSTEM",
                details={
                    "exception_type": exc_type,
                    "exception_message": exc_msg[:500],
                    "task_name": task_name,
                    "context": context
                },
                status="failure"
            )
        except Exception as log_err:
            logger.error(f"Failed to log exception to audit: {log_err}")
    
    async def _invoke_callbacks(
        self,
        exc: Exception,
        context: Optional[Dict],
        task_name: Optional[str]
    ):
        """调用注册的异常回调"""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(exc, context, task_name)
                else:
                    callback(exc, context, task_name)
            except Exception as cb_err:
                logger.error(f"Exception callback error: {cb_err}")
    
    def add_callback(self, callback: Callable):
        """添加异常回调"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """移除异常回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def create_task(
        self,
        coro,
        *,
        name: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> asyncio.Task:
        """
        创建带异常捕捉的异步任务
        
        替代 asyncio.create_task()，自动捕捉并记录异常
        
        Args:
            coro: 协程对象
            name: 任务名称
            context: 上下文信息
            
        Returns:
            asyncio.Task 对象
        """
        async def wrapped():
            try:
                return await coro
            except asyncio.CancelledError:
                raise  # 允许取消传播
            except Exception as e:
                await self.handle_exception(e, context, name)
                raise  # 重新抛出以便调用者处理
        
        return asyncio.create_task(wrapped(), name=name)
    
    def task_wrapper(self, name: Optional[str] = None):
        """
        装饰器: 为异步函数添加异常捕捉
        
        Usage:
            @exception_handler.task_wrapper("my_task")
            async def my_task():
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    await self.handle_exception(
                        e, 
                        context={"args": str(args)[:100], "kwargs": str(kwargs)[:100]},
                        task_name=name or func.__name__
                    )
                    raise
            return wrapper
        return decorator
    
    def get_stats(self) -> Dict:
        """获取异常统计信息"""
        now = datetime.utcnow()
        active_aggregates = [
            {
                "hash": agg.exception_hash,
                "count": agg.count,
                "first_seen": agg.first_occurrence.isoformat(),
                "last_seen": agg.last_occurrence.isoformat(),
                "sample": agg.sample_traceback[:500]
            }
            for agg in self._aggregates.values()
            if now - agg.last_occurrence < self.AGGREGATION_WINDOW
        ]
        
        return {
            "total_aggregates": len(self._aggregates),
            "active_aggregates": len(active_aggregates),
            "callbacks_count": len(self._callbacks),
            "aggregation_window_minutes": self.AGGREGATION_WINDOW.total_seconds() / 60,
            "recent_exceptions": active_aggregates[:10]
        }


# 全局单例
exception_handler = GlobalExceptionHandler()
