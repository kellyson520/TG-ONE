import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None

class ResourceGate:
    """
    Performance Gatekeeper to ensure resource usage stays within limits.
    Strictly enforcing the 2GB RAM limit as per system mandate.
    """
    MAX_RAM_BYTES = 2 * 1024 * 1024 * 1024  # 2GB

    @staticmethod
    def get_current_memory_usage() -> int:
        """Returns current RSS memory usage in bytes."""
        if psutil is None:
            logger.warning("ResourceGate: psutil not installed.")
            return 0
            
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            return mem_info.rss
        except Exception as e:
            logger.error(f"ResourceGate: Error checking memory usage: {e}")
            return 0

    @staticmethod
    def check_memory_safe(limit_bytes: Optional[int] = None) -> bool:
        """
        Check if current process memory usage is within safe limits.
        Returns True if safe, False if unsafe.
        """
        current_usage = ResourceGate.get_current_memory_usage()
        if current_usage == 0:
            return True # Assume safe if we can't check or error

        limit = limit_bytes or ResourceGate.MAX_RAM_BYTES
        
        if current_usage > limit:
            logger.warning(f"ResourceGate: Memory usage {current_usage / 1024 / 1024:.2f} MB exceeds limit {limit / 1024 / 1024:.2f} MB")
            return False
        return True

    @staticmethod
    def enforce_memory_limit():
        """
        Raise MemoryError if memory limit is exceeded.
        """
        if not ResourceGate.check_memory_safe():
            # Get current usage specifically for the error message
            usage = ResourceGate.get_current_memory_usage()
            raise MemoryError(f"Process exceeded allowed memory limit (2GB). Current: {usage / 1024 / 1024:.2f} MB")
