"""
优雅关闭协调器 (Graceful Shutdown Coordinator)

提供统一的资源清理机制，确保系统在关闭时能够：
1. 按优先级顺序执行清理任务
2. 控制超时，防止无限阻塞
3. 记录清理过程日志
4. 处理清理异常

Author: System
Created: 2026-01-14
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Awaitable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CleanupTask:
    """清理任务定义"""
    callback: Callable[[], Awaitable[None]]
    priority: int  # 0-9, 0 最高优先级
    timeout: float  # 单个任务超时 (秒)
    name: str  # 任务名称


class ShutdownCoordinator:
    """
    优雅关闭协调器
    
    负责管理系统关闭时的资源清理流程，确保：
    - 按优先级顺序执行清理
    - 控制总超时时间
    - 记录清理过程
    - 处理清理异常
    
    使用示例:
        coordinator = ShutdownCoordinator(total_timeout=30.0)
        
        # 注册清理回调
        coordinator.register_cleanup(
            callback=stop_web_server,
            priority=0,
            timeout=2.0,
            name="web_server"
        )
        
        # 执行关闭
        success = await coordinator.shutdown()
    """
    
    def __init__(self, total_timeout: float = 30.0):
        """
        初始化协调器
        
        Args:
            total_timeout: 总超时时间 (秒)，超过此时间将强制退出
        """
        self._tasks: List[CleanupTask] = []
        self._total_timeout = total_timeout
        self._is_shutting_down = False
        self._lock = asyncio.Lock()
        self._shutdown_start_time: Optional[float] = None
        
    def register_cleanup(
        self,
        callback: Callable[[], Awaitable[None]],
        priority: int = 5,
        timeout: float = 5.0,
        name: Optional[str] = None
    ) -> None:
        """
        注册清理回调
        
        Args:
            callback: 异步清理函数
            priority: 优先级 (0-9, 0 最高)
            timeout: 单个回调超时 (秒)
            name: 回调名称 (用于日志)
            
        Raises:
            ValueError: 如果优先级不在 0-9 范围内
        """
        if not 0 <= priority <= 9:
            raise ValueError(f"Priority must be 0-9, got {priority}")
        
        if name is None:
            name = callback.__name__
        
        task = CleanupTask(
            callback=callback,
            priority=priority,
            timeout=timeout,
            name=name
        )
        
        self._tasks.append(task)
        logger.debug(f"注册清理任务: {name} (优先级: {priority}, 超时: {timeout}s)")
    
    def is_shutting_down(self) -> bool:
        """
        检查是否正在关闭
        
        Returns:
            bool: True 如果正在关闭
        """
        return self._is_shutting_down
    
    async def shutdown(self) -> bool:
        """
        执行优雅关闭
        
        按优先级顺序执行所有注册的清理任务，每个任务都有独立的超时控制。
        如果总时间超过 total_timeout，将跳过剩余任务。
        
        Returns:
            bool: True 如果所有任务成功完成，False 如果有任务失败或超时
        """
        # 防止重复关闭
        async with self._lock:
            if self._is_shutting_down:
                logger.info("系统关闭流程已由其他任务触发，忽略此次重复调用。")
                return True
            self._is_shutting_down = True
        
        self._shutdown_start_time = time.time()
        logger.info(f"[SHUTDOWN] 开始优雅关闭流程... (总超时: {self._total_timeout}s, 任务数: {len(self._tasks)})")
        
        # 按优先级排序 (0 最高)
        sorted_tasks = sorted(self._tasks, key=lambda t: t.priority)
        
        success_count = 0
        failure_count = 0
        timeout_count = 0
        
        for task in sorted_tasks:
            # 检查总超时
            elapsed = time.time() - self._shutdown_start_time
            remaining = self._total_timeout - elapsed
            
            if remaining <= 0:
                logger.warning(f"[SHUTDOWN] 总超时 ({self._total_timeout}s)，跳过剩余 {len(sorted_tasks) - success_count - failure_count - timeout_count} 个任务")
                break
            
            # 使用剩余时间和任务超时的较小值
            effective_timeout = min(task.timeout, remaining)
            
            try:
                logger.info(f"[SHUTDOWN] 执行清理: {task.name} (优先级: {task.priority}, 超时: {effective_timeout:.1f}s)")
                task_start = time.time()
                
                await asyncio.wait_for(task.callback(), timeout=effective_timeout)
                
                task_duration = time.time() - task_start
                logger.info(f"[SHUTDOWN] ✓ 清理完成: {task.name} (耗时: {task_duration:.2f}s)")
                success_count += 1
                
            except asyncio.TimeoutError:
                logger.error(f"[SHUTDOWN] ✗ 清理超时: {task.name} (超时: {effective_timeout:.1f}s)")
                timeout_count += 1
                
            except Exception as e:
                logger.error(f"[SHUTDOWN] ✗ 清理失败: {task.name}, 错误: {e}", exc_info=True)
                failure_count += 1
        
        total_duration = time.time() - self._shutdown_start_time
        all_success = (failure_count == 0 and timeout_count == 0)
        
        logger.info(
            f"[SHUTDOWN] 优雅关闭完成 "
            f"(成功: {success_count}, 失败: {failure_count}, 超时: {timeout_count}, "
            f"总耗时: {total_duration:.2f}s, 状态: {'✓' if all_success else '✗'})"
        )
        
        return all_success
    
    def get_shutdown_duration(self) -> Optional[float]:
        """
        获取关闭流程已运行时间
        
        Returns:
            float: 已运行秒数，如果未开始则返回 None
        """
        if self._shutdown_start_time is None:
            return None
        return time.time() - self._shutdown_start_time


# 全局单例
_global_coordinator: Optional[ShutdownCoordinator] = None


def get_shutdown_coordinator() -> ShutdownCoordinator:
    """
    获取全局关闭协调器单例
    
    Returns:
        ShutdownCoordinator: 全局协调器实例
    """
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = ShutdownCoordinator(total_timeout=30.0)
    return _global_coordinator


def register_cleanup(
    callback: Callable[[], Awaitable[None]],
    priority: int = 5,
    timeout: float = 5.0,
    name: Optional[str] = None
) -> None:
    """
    便捷函数：向全局协调器注册清理回调
    
    Args:
        callback: 异步清理函数
        priority: 优先级 (0-9, 0 最高)
        timeout: 单个回调超时 (秒)
        name: 回调名称 (用于日志)
    """
    coordinator = get_shutdown_coordinator()
    coordinator.register_cleanup(callback, priority, timeout, name)
