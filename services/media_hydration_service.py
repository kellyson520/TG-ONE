import asyncio
import os
import logging
from typing import Dict, Optional
from core.constants import TEMP_DIR

logger = logging.getLogger(__name__)

class MediaStatus:
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    FAILED = "failed"

class MediaHydrationService:
    """
    Manage lifecycle of local media files: Download -> Use -> Cleanup.
    Prevents duplicate downloads and ensures cleanup.
    """
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._status: Dict[str, str] = {}
        self._paths: Dict[str, str] = {}
        self._active_users: Dict[str, int] = {} # Reference counting
        self._global_lock = asyncio.Lock()

    async def _get_lock(self, file_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if file_id not in self._locks:
                self._locks[file_id] = asyncio.Lock()
            return self._locks[file_id]

    async def hydration_context(self, message, file_id: str = None):
        """
        Context manager for hydrated media.
        Usage:
            async with media_hydration.hydration_context(msg, file_id) as path:
                # use path
        """
        if not file_id:
            file_id = f"{message.chat_id}_{message.id}"
            
        path = await self.hydrate(message, file_id)
        try:
            yield path
        finally:
            await self.release(file_id)

    async def hydrate(self, message, file_id: str) -> Optional[str]:
        """
        Ensure media is downloaded and return path.
        """
        lock = await self._get_lock(file_id)
        
        async with lock:
            # Increment ref count
            self._active_users[file_id] = self._active_users.get(file_id, 0) + 1
            
            if self._status.get(file_id) == MediaStatus.DOWNLOADED:
                if os.path.exists(self._paths[file_id]):
                    return self._paths[file_id]
                else:
                    # File gone? Reset.
                    self._status.pop(file_id)
            
            # Start download
            self._status[file_id] = MediaStatus.PENDING
            try:
                path = await message.download_media(file=TEMP_DIR)
                if path:
                    self._paths[file_id] = path
                    self._status[file_id] = MediaStatus.DOWNLOADED
                    logger.debug(f"Media hydrated: {file_id} -> {path}")
                    return path
                else:
                    self._status[file_id] = MediaStatus.FAILED
                    return None
            except Exception as e:
                logger.error(f"Media hydration failed for {file_id}: {e}")
                self._status[file_id] = MediaStatus.FAILED
                return None

    async def release(self, file_id: str):
        """
        Release reference. Cleanup if no active users.
        """
        async with self._global_lock: # Simplified locking for dict access
            if file_id in self._active_users:
                self._active_users[file_id] -= 1
                
                if self._active_users[file_id] <= 0:
                    # Cleanup
                    path = self._paths.get(file_id)
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                            logger.debug(f"Media released and cleaned: {file_id}")
                        except Exception as e:
                            logger.error(f"Failed to clean media {path}: {e}")
                    
                    self._locks.pop(file_id, None)
                    self._status.pop(file_id, None)
                    self._paths.pop(file_id, None)
                    self._active_users.pop(file_id, None)

media_hydration_service = MediaHydrationService()
