import logging

logger = logging.getLogger(__name__)

class AIMDScheduler:
    """
    AIMD (Additive Increase, Multiplicative Decrease) 调度算法实现。
    
    用于动态调整轮询频率（如 RSS 源、API 检查等）：
    - 成功获取新内容时：乘法减小间隔时间 (Multiplicative Decrease of Interval) -> 频率加快。
    - 未能获取新内容时：加法增加间隔时间 (Additive Increase of Interval) -> 频率减慢。
    """
    def __init__(
        self, 
        min_interval: float = 60,      # 最小间隔 (秒)
        max_interval: float = 3600,    # 最大间隔 (秒)
        increment: float = 60,         # 加法增量 (秒)
        multiplier: float = 0.5        # 乘法因子
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.increment = increment
        self.multiplier = multiplier
        self.current_interval = min_interval

    def update(self, found_new_content: bool) -> float:
        """
        根据执行结果更新间隔。
        
        Args:
            found_new_content: 是否发现新内容
            
        Returns:
            调整后的下一次执行间隔 (秒)
        """
        if found_new_content:
            # 乘法减小 (加速)
            new_interval = self.current_interval * self.multiplier
            self.current_interval = max(self.min_interval, new_interval)
            logger.debug(f"[AIMD] 发现更新, 间隔缩减 -> {self.current_interval:.1f}s")
        else:
            # 加法增加 (减速)
            new_interval = self.current_interval + self.increment
            self.current_interval = min(self.max_interval, new_interval)
            logger.debug(f"[AIMD] 无更新, 间隔增加 -> {self.current_interval:.1f}s")
            
        return self.current_interval

    def reset(self):
        """重置为初始状态"""
        self.current_interval = self.min_interval
