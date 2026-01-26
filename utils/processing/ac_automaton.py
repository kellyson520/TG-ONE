
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.algorithms.ac_automaton`.
"""
import warnings
warnings.warn("Importing from utils.processing.ac_automaton is deprecated. Use core.algorithms.ac_automaton instead.", DeprecationWarning, stacklevel=2)

from core.algorithms.ac_automaton import ACAutomaton
