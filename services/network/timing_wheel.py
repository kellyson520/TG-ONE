import logging
import asyncio
import math
import time
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

class TimingWheelTask:
    def __init__(self, task_id: str, _delay_ticks: int, callback: Callable, *args, **kwargs):
        self.task_id = task_id
        self.remaining_rounds = 0 # 剩余轮数 (用于处理超过一圈的延迟)
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.cancelled = False

class HashedTimingWheel:
    """
    Hashed Timing Wheel (时间轮)
    用于高效调度大量定时任务（如 RSS 刷新、自动删除消息、推送重试等）。
    相比于原生的 asyncio.sleep，能显著减少定时器的维护开销。
    """
    def __init__(self, tick_ms: int = 1000, slots: int = 60):
        """
        Args:
            tick_ms: 每一个刻度的时间长度 (ms)
            slots: 时间轮的槽位数量
        """
        self.tick_ms = tick_ms / 1000.0
        self.slots = slots
        self.wheel: List[Set[TimingWheelTask]] = [set() for _ in range(slots)]
        self.current_slot = 0
        self.tasks: Dict[str, TimingWheelTask] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._new_task_event: Optional[asyncio.Event] = None

    def add_task(self, task_id: str, delay_seconds: float, callback: Callable, *args, **kwargs) -> str:
        """添加一个定时任务"""
        if task_id in self.tasks:
            self.cancel_task(task_id)

        total_ticks = math.ceil(delay_seconds / self.tick_ms)
        if total_ticks <= 0:
            total_ticks = 1
            
        rounds = total_ticks // self.slots
        target_slot = (self.current_slot + total_ticks) % self.slots
        
        task = TimingWheelTask(task_id, total_ticks, callback, *args, **kwargs)
        task.remaining_rounds = rounds
        
        # 记录到槽位
        self.wheel[target_slot].add(task)
        self.tasks[task_id] = task
        if self._new_task_event:
            self._new_task_event.set()
        return task_id

    def cancel_task(self, task_id: str):
        """取消一个任务"""
        if task_id in self.tasks:
            self.tasks[task_id].cancelled = True
            # 注意：这里我们不立即从 wheel 中删除以保持 O(1)
            # 任务执行器在扫描到时会根据 cancelled 标志忽略它

    async def start(self):
        """启动刻度推进循环"""
        if self._running:
            return
        self._running = True
        if self._new_task_event is None:
            self._new_task_event = asyncio.Event()
        self._loop_task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """停止时间轮"""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError as e:
                logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

    async def _run_loop(self):
        while self._running:
            await self._wait_for_tasks()
            if not self._running:
                break

            start_time = time.time()

            # 处理当前槽位的任务
            slot_tasks = self.wheel[self.current_slot]
            to_remove = set()
            ready_tasks = []

            for task in slot_tasks:
                if task.cancelled:
                    to_remove.add(task)
                    continue

                if task.remaining_rounds > 0:
                    task.remaining_rounds -= 1
                else:
                    ready_tasks.append(task)
                    to_remove.add(task)

            # 清理已完成/已取消的任务
            for t in to_remove:
                slot_tasks.remove(t)
                if self.tasks.get(t.task_id) is t:
                    del self.tasks[t.task_id]

            # 异步执行到期的任务
            for t in ready_tasks:
                callback_task = asyncio.create_task(t.callback(*t.args, **t.kwargs))
                callback_task.add_done_callback(self._log_callback_error)

            # 推进指针
            self.current_slot = (self.current_slot + 1) % self.slots

            if not self._has_active_tasks():
                continue

            # 等待下一个刻度
            elapsed = time.time() - start_time
            sleep_time = max(0, self.tick_ms - elapsed)
            await asyncio.sleep(sleep_time)

    async def _wait_for_tasks(self):
        if self._has_active_tasks():
            return

        self._prune_cancelled_tasks()
        if self._has_active_tasks():
            return

        if self._new_task_event is None:
            self._new_task_event = asyncio.Event()

        self._new_task_event.clear()
        if not self._has_active_tasks():
            await self._new_task_event.wait()

    def _has_active_tasks(self) -> bool:
        return any(not task.cancelled for task in self.tasks.values())

    @staticmethod
    def _log_callback_error(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Timing wheel callback failed")

    def _prune_cancelled_tasks(self):
        for slot in self.wheel:
            cancelled = {task for task in slot if task.cancelled}
            if not cancelled:
                continue
            slot.difference_update(cancelled)
            for task in cancelled:
                if self.tasks.get(task.task_id) is task:
                    del self.tasks[task.task_id]

    def get_stats(self) -> Dict[str, Any]:
        """获取时间轮统计信息"""
        total_tasks = len(self.tasks)
        active_tasks = sum(1 for t in self.tasks.values() if not t.cancelled)
        
        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "current_slot": self.current_slot,
            "is_running": self._running,
            "total_slots": self.slots
        }
