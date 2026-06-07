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
        self._running = False
        self._activity_event: Optional[asyncio.Event] = None
        self._on_sleep_callbacks: List[Callable[[], None]] = []
        self._on_wake_callbacks: List[Callable[[], None]] = []
        
    def record_activity(self):
        """Call this whenever meaningful activity occurs (message received, UI request, etc.)"""
        self._last_activity = time.time()
        if self._activity_event:
            self._activity_event.set()
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
        if self._running:
            return

        logger.info("SleepManager: Monitor started.")
        self._running = True
        if self._activity_event is None:
            self._activity_event = asyncio.Event()

        while self._running:
            try:
                if self._is_sleeping:
                    self._activity_event.clear()
                    await self._activity_event.wait()
                    continue

                self._activity_event.clear()
                idle_remaining = self._time_until_sleep()
                if idle_remaining <= 0:
                    await self._go_to_sleep()
                    continue

                try:
                    await asyncio.wait_for(
                        self._activity_event.wait(),
                        timeout=idle_remaining,
                    )
                except asyncio.TimeoutError:
                    logger.debug(
                        "SleepManager: Idle wait timed out after %.3fs.",
                        idle_remaining,
                    )
            except asyncio.CancelledError:
                logger.info("SleepManager: Monitor stopping (cancelled).")
                break
            except Exception as e:
                logger.error(f"SleepManager error: {e}")
        self._running = False

    def _time_until_sleep(self) -> float:
        idle_for = time.time() - self._last_activity
        return max(0.0, self.SLEEP_TIMEOUT - idle_for)

    def stop(self):
        """Request monitor shutdown and wake it if it is waiting."""
        self._running = False
        if self._activity_event:
            self._activity_event.set()

    def register_on_sleep(self, callback: Callable):
        self._on_sleep_callbacks.append(callback)

    def register_on_wake(self, callback: Callable):
        self._on_wake_callbacks.append(callback)
        
    @property
    def is_sleeping(self) -> bool:
        return self._is_sleeping

sleep_manager = SleepManager()
