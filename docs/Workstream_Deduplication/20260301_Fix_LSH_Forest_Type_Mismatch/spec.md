# SPEC - Fix LSH Forest Type Mismatch (TypeError)

## 📋 Problem Analysis
- **Observed Behavior**: `bisect_left` in `lsh_forest.py` fails with `TypeError: '<' not supported between instances of 'list' and 'tuple'`.
- **Root Cause**: Elements in `self.trees` are `list` instances (JSON/Orjson conversion of tuples) while the search key is a `tuple`.
- **Primary Source**: `SmartDeduplicator._hibernate_state` saves tuples to JSON-serialized state. `_wakeup_state` attempts conversion back, but some chat_id indices may have been corrupted or missed.

## 🛠️ Proposed Solution

### 1. Robust Type Restoration (Fix `engine.py`)
In `SmartDeduplicator._wakeup_state`, we must ensure *every* element of *every* tree is converted from `[int, str]` (JSON) back to `(int, str)` (Tuple).
Current code:
```python
f.trees = [[tuple(item) for item in tree] for tree in raw_trees]
```
This is correct, but let's check if `raw_trees` or `tree` can be anything else.
We should also handle cases where `num_trees` changed.

### 2. Guarded Comparison (Fix `lsh_forest.py`)
In `LSHForest.query`, we can force the comparison key to match the type of elements in the tree *or* ensure the tree elements are always tuples.
Better: **Fix the state during query** if corruption is detected, or at least handle it gracefully.
Also, the current `query` method in `lsh_forest.py` is redundant (two loops). One loop finds candidates, the other verified. It should be consolidated into a single clean pass.

### 3. TDD Reproduction
Create `tests/repro_lsh_mismatch.py`:
1. Initialize `LSHForest`.
2. Mock a "hibernated" state (manually insert a `list` into `trees`).
3. Call `query` with a `tuple` key.
4. Fail if `TypeError` occurs.
5. Apply fixes.
6. Verify no `TypeError`.

## 📌 Architecture Guard
- **No Layering Violation**: `lsh_forest.py` remains a pure algorithm module.
- **No Performance Regression**: Keep the tight binary search loop.
- **Memory Limit**: All tests must stay under **2GB RAM**.
- **Silent Failures**: Log warning if corruption is detected.

## 💼 Reliability Matrix
| Feature | Risk | Mitigation |
|:---|-:|-:|
| Hibernation | Type mismatch | Robust tuple cast in `_wakeup_state`. |
| Fresh Search | Inconsistent types | Automatic type-sensing in `query` or strict `add`. |
| Top-K Search | Redundant loops | Consolidate `query` passes. |
