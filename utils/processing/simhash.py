
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.algorithms.simhash`.
"""
import warnings
warnings.warn("Importing from utils.processing.simhash is deprecated. Use core.algorithms.simhash instead.", DeprecationWarning, stacklevel=2)

from core.algorithms.simhash import SimHash, compute_simhash
