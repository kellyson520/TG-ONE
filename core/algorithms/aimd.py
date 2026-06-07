import logging

logger = logging.getLogger(__name__)


class AIMDScheduler:
    """
    AIMD (Additive Increase, Multiplicative Decrease) interval scheduler.

    Used by background flush/poll loops to speed up when useful work appears and
    slow down when the system is idle.
    """

    def __init__(
        self,
        min_interval: float = 60,
        max_interval: float = 3600,
        increment: float = 60,
        multiplier: float = 0.5,
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.increment = increment
        self.multiplier = multiplier
        self.current_interval = min_interval

    def update(self, found_new_content: bool) -> float:
        """
        Update and return the next interval.

        Args:
            found_new_content: Whether the previous run found useful work.
        """
        if found_new_content:
            new_interval = self.current_interval * self.multiplier
            self.current_interval = max(self.min_interval, new_interval)
            logger.debug("[AIMD] content found, interval -> %.1fs", self.current_interval)
        else:
            new_interval = self.current_interval + self.increment
            self.current_interval = min(self.max_interval, new_interval)
            logger.debug("[AIMD] idle, interval -> %.1fs", self.current_interval)

        return self.current_interval

    def reset(self):
        """Reset to the minimum interval."""
        self.current_interval = self.min_interval
