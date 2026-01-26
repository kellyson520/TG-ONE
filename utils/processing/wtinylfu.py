
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.cache.wtinylfu`.
"""
import warnings
warnings.warn("Importing from utils.processing.wtinylfu is deprecated. Use core.cache.wtinylfu instead.", DeprecationWarning, stacklevel=2)

from core.cache.wtinylfu import WTinyLFU
