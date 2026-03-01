# TODO - Fix LSH Forest Type Mismatch (TypeError)

## 📋 Task Details
- **Issue**: `TypeError: '<' not supported between instances of 'list' and 'tuple'` in `lsh_forest.py` during `bisect_left`.
- **Root Cause**: Likely JSON/Orjson serialization converting tuples to lists during hibernation, and a gap in restoration or inconsistent query keys.
- **Reference Task ID**: 967772
- **Module**: `core.algorithms.lsh_forest`, `services.dedup.engine`

## 🚀 Plan (PSB Protocol)

### Phase 1: Plan & Analysis
- [x] Analyze log and traceback
- [x] Identify root cause in `SmartDeduplicator._wakeup_state` and `LSHForest.query`
- [ ] Create `spec.md` and this `todo.md`

### Phase 2: Setup (Reproduction)
- [ ] Create a small test script `tests/repro_lsh_mismatch.py` to trigger the error with mixed types in `tree`.
- [ ] Verify error occurs when list meets tuple in `bisect`.

### Phase 3: Build (Implementation)
- [ ] **Fix `engine.py`**:
    - Ensure `_wakeup_state` and `_hibernate_state` are perfectly symmetrical.
    - Check if any other place modifies `lsh_forests`.
- [ ] **Fix `lsh_forest.py`**:
    - Clean up redundant code in `query` (remove the double loop).
    - Add a `_ensure_tuple` wrapper or explicit conversion in `query`.
    - Make `add` more robust.

### Phase 4: Verify (Testing)
- [ ] Run `tests/repro_lsh_mismatch.py` -> Should PASS now.
- [ ] Run `pytest tests/unit/utils/test_lsh_forest.py` (if exists and is small).
- [ ] Memory Audit: Ensure RAM < 2GB.

### Phase 5: Report
- [ ] Generate `report.md`.
- [ ] Sync `docs/tree.md`.
- [ ] Final check of workspace hygiene.
