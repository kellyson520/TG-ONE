import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Set

class TimingWheelTask:
    def __init__(self, task_id: str, delay_ticks: int, callback: Callable, *args, **kwargs):
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

    def add_task(self, task_id: str, delay_seconds: float, callback: Callable, *args, **kwargs) -> str:
        """添加一个定时任务"""
        total_ticks = int(delay_seconds / self.tick_ms)
        if total_ticks <= 0:
            total_ticks = 1
            
        rounds = total_ticks // self.slots
        target_slot = (self.current_slot + total_ticks) % self.slots
        
        task = TimingWheelTask(task_id, total_ticks, callback, *args, **kwargs)
        task.remaining_rounds = rounds
        
        # 记录到槽位
        self.wheel[target_slot].add(task)
        self.tasks[task_id] = task
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
        self._loop_task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """停止时间轮"""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        while self._running:
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
                if t.task_id in self.tasks:
                    del self.tasks[t.task_id]
                    
            # 异步执行到期的任务
            for t in ready_tasks:
                asyncio.create_task(t.callback(*t.args, **t.kwargs))
                
            # 推进指针
            self.current_slot = (self.current_slot + 1) % self.slots
            
            # 等待下一个刻度
            elapsed = time.time() - start_time
            sleep_time = max(0, self.tick_ms - elapsed)
            await asyncio.sleep(sleep_time)

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
