
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.algorithms.bloom_filter`.
"""
import warnings
warnings.warn("Importing from utils.processing.bloom_filter is deprecated. Use core.algorithms.bloom_filter instead.", DeprecationWarning, stacklevel=2)

from core.algorithms.bloom_filter import BloomFilter
