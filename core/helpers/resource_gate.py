import os
import logging
from typing import Optional

from core.helpers.memory_policy import resolve_process_memory_thresholds

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None

class ResourceGate:
    """
    Performance Gatekeeper to ensure resource usage stays within configured limits.
    """
    DEFAULT_MAX_RAM_BYTES = 768 * 1024 * 1024

    @staticmethod
    def _configured_limit_bytes() -> int:
        try:
            from core.config import settings
            _, critical_mb = resolve_process_memory_thresholds(
                int(settings.MEMORY_WARNING_THRESHOLD_MB),
                int(settings.MEMORY_CRITICAL_THRESHOLD_MB),
            )
            return critical_mb * 1024 * 1024
        except Exception:
            return ResourceGate.DEFAULT_MAX_RAM_BYTES

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

        limit = limit_bytes or ResourceGate._configured_limit_bytes()
        
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
            limit_mb = ResourceGate._configured_limit_bytes() / 1024 / 1024
            raise MemoryError(
                f"Process exceeded allowed memory limit ({limit_mb:.0f}MB). "
                f"Current: {usage / 1024 / 1024:.2f} MB"
            )
