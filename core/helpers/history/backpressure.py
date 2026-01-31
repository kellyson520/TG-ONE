"""
背压控制器
防止历史消息处理过快导致队列积压
"""
import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BackpressureController:
    """背压控制器 - 动态调整处理速度"""

    def __init__(
        self,
        max_pending: int = 1000,
        check_interval: int = 100,
        pause_threshold: float = 0.8,
        resume_threshold: float = 0.5,
    ):
        """
        初始化背压控制器

        Args:
            max_pending: 最大待处理任务数
            check_interval: 检查间隔(处理多少条消息后检查一次)
            pause_threshold: 暂停阈值(队列利用率超过此值时暂停)
            resume_threshold: 恢复阈值(队列利用率低于此值时恢复正常)
        """
        self.max_pending = max_pending
        self.check_interval = check_interval
        self.pause_threshold = pause_threshold
        self.resume_threshold = resume_threshold

        # 统计信息
        self.total_pauses = 0
        self.total_pause_time = 0.0

    async def check_and_wait(
        self, task_repo: Any, processed_count: int, cancel_event: Optional[asyncio.Event] = None
    ) -> bool:
        """
        检查队列状态并根据需要暂停

        Args:
            task_repo: 任务仓库
            processed_count: 已处理消息数
            cancel_event: 取消事件

        Returns:
            bool: True=继续处理, False=已取消
        """
        # 只在检查间隔时执行
        if processed_count % self.check_interval != 0:
            return True

        # 检查是否取消
        if cancel_event and cancel_event.is_set():
            return False

        try:
            # 获取队列状态
            status = await task_repo.get_queue_status()
            pending = status.get("active_queues", 0)
            utilization = pending / self.max_pending if self.max_pending > 0 else 0

            # 根据利用率决定等待时间
            wait_time = self._calculate_wait_time(utilization)

            if wait_time > 0:
                self.total_pauses += 1
                self.total_pause_time += wait_time

                logger.info(
                    f"🔄 背压控制: 队列利用率 {utilization:.1%} "
                    f"({pending}/{self.max_pending}), 暂停 {wait_time}秒"
                )

                # 分段等待，以便响应取消事件
                await self._interruptible_sleep(wait_time, cancel_event)

                # 再次检查是否取消
                if cancel_event and cancel_event.is_set():
                    return False

            return True

        except Exception as e:
            logger.warning(f"背压检查失败: {e}, 使用默认延迟")
            await asyncio.sleep(0.2)
            return True

    def _calculate_wait_time(self, utilization: float) -> float:
        """
        根据队列利用率计算等待时间

        Args:
            utilization: 队列利用率 (0.0 - 1.0)

        Returns:
            float: 等待时间(秒)
        """
        if utilization >= 1.0:
            # 队列满载，长时间暂停
            return 5.0
        elif utilization >= 0.95:
            # 接近满载
            return 3.0
        elif utilization >= self.pause_threshold:
            # 超过暂停阈值
            return 2.0
        elif utilization >= self.resume_threshold:
            # 队列较满，减速
            return 0.5
        else:
            # 队列空闲，正常处理
            return 0.1

    async def _interruptible_sleep(
        self, duration: float, cancel_event: Optional[asyncio.Event] = None
    ) -> None:
        """
        可中断的睡眠

        Args:
            duration: 睡眠时长(秒)
            cancel_event: 取消事件
        """
        if not cancel_event:
            await asyncio.sleep(duration)
            return

        # 分段睡眠，每0.5秒检查一次取消事件
        elapsed = 0.0
        step = 0.5

        while elapsed < duration:
            if cancel_event.is_set():
                return

            sleep_time = min(step, duration - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_pauses": self.total_pauses,
            "total_pause_time": round(self.total_pause_time, 2),
            "average_pause_time": (
                round(self.total_pause_time / self.total_pauses, 2)
                if self.total_pauses > 0
                else 0
            ),
            "config": {
                "max_pending": self.max_pending,
                "check_interval": self.check_interval,
                "pause_threshold": self.pause_threshold,
                "resume_threshold": self.resume_threshold,
            },
        }

    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.total_pauses = 0
        self.total_pause_time = 0.0

    def __repr__(self) -> str:
        return (
            f"<BackpressureController "
            f"max_pending={self.max_pending} "
            f"pauses={self.total_pauses}>"
        )
