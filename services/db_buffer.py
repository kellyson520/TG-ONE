import asyncio
import time
from collections import deque
from typing import Any, List, Optional


from core.logging import get_logger

logger = get_logger(__name__)


class MessageBuffer:
    """
    High-performance double-ended queue buffer for Group Commit.
    Thread-safe (Async-safe) storage for ORM objects.
    """

    def __init__(self, batch_size: int = 50, flush_interval: float = 5.0):
        self._buffer: deque = deque()
        self._lock = asyncio.Lock()
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._last_flush_time = time.time()
        self._coordinator: Optional['GroupCommitCoordinator'] = None

    def set_coordinator(self, coordinator: 'GroupCommitCoordinator'):
        self._coordinator = coordinator

    async def add(self, item: Any):
        """Add an item to the buffer. Triggers flush if batch size exceeded."""
        async with self._lock:
            self._buffer.append(item)
            current_size = len(self._buffer)
        
        # Check trigger outside lock to avoid holding it during flush
        if current_size >= self._batch_size:
            logger.debug(f"Buffer size {current_size} >= {self._batch_size}, triggering flush")
            if self._coordinator:
                await self._coordinator.trigger_flush()

    async def get_and_clear(self) -> List[Any]:
        """Retrieve all items and clear buffer atomically."""
        async with self._lock:
            if not self._buffer:
                return []
            
            items = list(self._buffer)
            self._buffer.clear()
            self._last_flush_time = time.time()
            return items

    def should_flush(self) -> bool:
        """Check if time based flush is needed."""
        return (time.time() - self._last_flush_time) >= self._flush_interval and len(self._buffer) > 0

    @property
    def size(self) -> int:
        return len(self._buffer)


class GroupCommitCoordinator:
    """
    Background task that monitors the buffer and performs async I/O.
    """

    def __init__(self, db_session_factory):
        self._buffer = MessageBuffer()
        self._buffer.set_coordinator(self)
        self._db_session_factory = db_session_factory
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._flush_event = asyncio.Event()

    @property
    def buffer(self) -> MessageBuffer:
        return self._buffer

    async def start(self):
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("GroupCommitCoordinator 已启动。")

    async def stop(self):
        """Stop the background loop and force final flush."""
        self._running = False
        if self._task:
            self._flush_event.set() # Wake up loop
            await self._task
            logger.info("GroupCommitCoordinator 已停止。")

    async def trigger_flush(self):
        """External signal to trigger immediate flush."""
        self._flush_event.set()

    async def _loop(self):
        while self._running:
            try:
                # Wait for trigger OR timeout (Time Trigger)
                try:
                    await asyncio.wait_for(self._flush_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass # Check time interval
                
                self._flush_event.clear()

                if self._buffer.should_flush() or self._buffer.size >= self._buffer._batch_size:
                    await self._flush()
                
            except Exception as e:
                logger.error(f"Error in GroupCommit loop: {e}", exc_info=True)
                await asyncio.sleep(1) # Backoff

        # Final flush on exit
        await self._flush()

    async def _flush(self):
        items = await self._buffer.get_and_clear()
        if not items:
            return

        count = len(items)
        start_time = time.time()
        
        try:
            # Create a new session for this transaction
            # Assuming db_session_factory context manager or callable
            # We need to adapt based on actual container usage. 
            # Looking at code, container.db_session() returns an async generator or context manager.
            
            # Since we are in a service method, usually we get session passed in, 
            # but here we are a background task, so we need to create one.
            async with self._db_session_factory() as session:
                session.add_all(items)
                await session.commit()
                
            duration = (time.time() - start_time) * 1000
            logger.info(f"Group Commit: 已刷入 {count} 条数据，耗时 {duration:.2f}ms")
            
        except Exception as e:
            logger.error(f"Failed to flush {count} items to DB: {e}", exc_info=True)
            # Strategy: Drop or Retry? 
            # For now, we log error. In production, maybe dump to disk (fallback).
            # If we want to retry, we would need to push back to buffer, but that risks infinite loop.
