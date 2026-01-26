
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.cache.unified_cache`.
"""
import warnings
warnings.warn("Importing from utils.processing.unified_cache is deprecated. Use core.cache.unified_cache instead.", DeprecationWarning, stacklevel=2)

from core.cache.unified_cache import UnifiedCache
