# Task Report: Enrich Forward Action Types and Fix Localization

## Summary
Successfully enriched the forwarding history records in the web panel. Added Chinese labels for actions and message types, fixed the processing time display issue for very fast tasks (0ms), and ensured filtered messages now include processing time data.

## Changes

### 1. Backend (Logic & Events)
- **`middlewares/filter.py`**: Added `duration` calculation to `FORWARD_FILTERED` event.
- **`middlewares/dedup.py`**: Added `FORWARD_FILTERED` event publication for duplicated messages, ensuring they are also logged in the history.
- **`core/container.py`**: 
    - Updated `_on_forward_filtered` to capture and log `duration`.
    - Localized system-generated result messages (e.g., "已转发", "按规则过滤").

### 2. Frontend (UI/UX)
- **`History.tsx`**:
    - **Localization**: Mapped all action types and message types to professional Chinese terms.
    - **UI Enrichment**: Restored the "Message Content" column in the history table for better visibility.
    - **Bug Fix**: Fixed conditional logic for `processing_time` to properly display `0ms` instead of hiding it.
    - **Visuals**: Updated Badge variants and colors for better status recognition.

## Verification Result
- Status Labels:
  - `success`/`forwarded` -> `已转发` (Green)
  - `filtered` -> `已过滤` (Gray)
  - `error` -> `失败` (Red)
- Message Types: Localized (e.g., "文本", "图片", "视频").
- Processing Time: Values like `0ms`, `5ms` now correctly appear for all record types including filtered ones.

## Files Modified
- `middlewares/filter.py`
- `middlewares/dedup.py`
- `core/container.py`
- `web_admin/frontend/src/pages/History.tsx`
