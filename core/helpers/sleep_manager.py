import asyncio
import logging
import time
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)

class SleepManager:
    """
    Manages system idle state and 'sleep' mode to conserve resources.
    The system is considered 'idle' if no relevant activity occurs for SLEEP_TIMEOUT seconds.
    """
    
    SLEEP_TIMEOUT: float = 300.0  # 5 minutes
    
    def __init__(self):
        self._last_activity = time.time()
        self._is_sleeping = False
        self._check_task: Optional[asyncio.Task] = None
        self._on_sleep_callbacks: List[Callable[[], None]] = []
        self._on_wake_callbacks: List[Callable[[], None]] = []
        
    def record_activity(self):
        """Call this whenever meaningful activity occurs (message received, UI request, etc.)"""
        self._last_activity = time.time()
        if self._is_sleeping:
            self._wake_up()
            
    def _wake_up(self):
        logger.info("SleepManager: Activity detected. Waking up.")
        self._is_sleeping = False
        for cb in self._on_wake_callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Error in wake callback: {e}")
                
    async def _go_to_sleep(self):
        if self._is_sleeping:
            return
        logger.info(f"SleepManager: No activity for {self.SLEEP_TIMEOUT}s. Entering Sleep Mode.")
        self._is_sleeping = True
        for cb in self._on_sleep_callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Error in sleep callback: {e}")

    async def start_monitor(self):
        logger.info("SleepManager: Monitor started.")
        while True:
            await asyncio.sleep(60)
            if not self._is_sleeping:
                if time.time() - self._last_activity > self.SLEEP_TIMEOUT:
                    await self._go_to_sleep()

    def register_on_sleep(self, callback: Callable):
        self._on_sleep_callbacks.append(callback)

    def register_on_wake(self, callback: Callable):
        self._on_wake_callbacks.append(callback)
        
    @property
    def is_sleeping(self) -> bool:
        return self._is_sleeping

sleep_manager = SleepManager()
