"""
历史消息处理进度跟踪器
提供详细的进度统计和预估功能
"""
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class HistoryTaskProgress:
    """历史任务进度跟踪器"""

    def __init__(self) -> None:
        self.total = 0  # 总消息数
        self.done = 0  # 已处理数
        self.forwarded = 0  # 已转发数
        self.filtered = 0  # 已过滤数
        self.failed = 0  # 失败数
        self.start_time = datetime.now()
        self.last_update_time = datetime.now()
        self.current_message_id = 0  # 当前处理的消息ID
        self.status = "running"  # running, paused, completed, failed, cancelled

    def update(self, **kwargs: Any) -> None:
        """更新进度信息"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_update_time = datetime.now()

    def increment(self, field: str, amount: int = 1) -> None:
        """增量更新指定字段"""
        if hasattr(self, field):
            current = getattr(self, field)
            setattr(self, field, current + amount)
        self.last_update_time = datetime.now()

    def get_percentage(self) -> float:
        """获取完成百分比"""
        if self.total == 0:
            return 0.0
        return (self.done / self.total) * 100

    def get_estimated_remaining(self) -> Optional[str]:
        """计算预估剩余时间"""
        if self.done == 0 or self.total == 0:
            return None

        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed == 0:
            return None

        speed = self.done / elapsed  # 条/秒
        remaining_items = self.total - self.done

        if remaining_items <= 0:
            return "即将完成"

        remaining_seconds = remaining_items / speed
        return self._format_duration(remaining_seconds)

    def get_processing_speed(self) -> float:
        """获取处理速度 (条/秒)"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed == 0:
            return 0.0
        return self.done / elapsed

    def get_elapsed_time(self) -> str:
        """获取已用时间"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return self._format_duration(elapsed)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """格式化时长显示"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "total": self.total,
            "done": self.done,
            "forwarded": self.forwarded,
            "filtered": self.filtered,
            "failed": self.failed,
            "percentage": round(self.get_percentage(), 2),
            "estimated_remaining": self.get_estimated_remaining(),
            "processing_speed": round(self.get_processing_speed(), 2),
            "elapsed_time": self.get_elapsed_time(),
            "current_message_id": self.current_message_id,
            "start_time": self.start_time.isoformat(),
            "last_update_time": self.last_update_time.isoformat(),
            "status": self.status,
        }

    def get_summary(self) -> str:
        """获取进度摘要文本"""
        percentage = self.get_percentage()
        speed = self.get_processing_speed()
        remaining = self.get_estimated_remaining()

        summary = f"进度: {self.done}/{self.total} ({percentage:.1f}%)\n"
        summary += f"速度: {speed:.1f} 条/秒\n"
        summary += f"已转发: {self.forwarded} | 已过滤: {self.filtered} | 失败: {self.failed}\n"

        if remaining:
            summary += f"预计剩余: {remaining}\n"

        summary += f"已用时间: {self.get_elapsed_time()}"

        return summary

    def __repr__(self) -> str:
        return (
            f"<HistoryTaskProgress "
            f"done={self.done}/{self.total} "
            f"({self.get_percentage():.1f}%) "
            f"status={self.status}>"
        )
