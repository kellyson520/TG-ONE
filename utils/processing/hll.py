
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.algorithms.hll`.
"""
import warnings
warnings.warn("Importing from utils.processing.hll is deprecated. Use core.algorithms.hll instead.", DeprecationWarning, stacklevel=2)

from core.algorithms.hll import HyperLogLog
