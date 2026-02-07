# Task: Complete Dedup Business Implementation

## Background
The `services/dedup` module was refactored, but some business logic was left as placeholders.
Specifically:
- `tools.calculate_simhash` is a dummy.
- `metrics.py` usage in strategies needs verification.
- `strategies/video.py` lacks partial hash check logic.
- `engine.py` lacks background video hash calculation logic.

## Goals
1.  **Implement SimHash**: Use `core.algorithms.simhash` in `services/dedup/tools.py`.
2.  **Implement Video Partial Hash**:
    - Add helper in `tools.py` to calculate partial hash from file/bytes.
    - Implement `strategies/video.py` to check partial hash IF available (or via cache).
    - Implement `engine.py`'s `_compute_and_save_video_hash_bg` to calculate and save hash.

## Plan
1.  Modify `services/dedup/tools.py` to import `core.algorithms.simhash`.
2.  Modify `services/dedup/tools.py` to add `calculate_video_partial_hash(path)`.
3.  Modify `services/dedup/strategies/video.py` to implement the logic.
4.  Modify `services/dedup/engine.py` to implement background task logic.
