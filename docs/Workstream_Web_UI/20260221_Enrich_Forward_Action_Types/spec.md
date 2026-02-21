# Specification: Forwarding Records UI Enhancement

## Background
The current web panel displays forwarding statuses in English/half-Chinese labels (`转发成功`, `执行失败`, `已过滤`) and lacks some processing time data for filtered messages. The user wants more intuitive Chinese labels and full coverage of processing time.

## Proposed Changes

### 1. Backend: Metadata Enrichment
- **`middlewares/filter.py`**: Calculate `duration` using `time.time() - ctx.start_time` and include it in the `FORWARD_FILTERED` event payload.
- **`core/container.py`**: Update `_on_forward_filtered` signature to accept `duration` from the event and pass it to `stats_repo.log_action`.

### 2. Frontend: UI Localization & Bug Fixes
- **Action Labels**:
  - `success` / `forwarded` -> `已转发` (Default Badge)
  - `error` -> `失败` (Destructive Badge)
  - `filtered` -> `已过滤` (Secondary Badge)
- **Message Type Mapping**:
  - Map English types (`text`, `photo`, `video`, etc.) to Chinese counterparts.
- **Processing Time Fix**:
  - Check `val !== null && val !== undefined` instead of just `val` to avoid hiding `0ms` processing times.

## Success Criteria
- All forwarding records show status in Chinese as requested.
- Message types are in Chinese.
- Processing time is displayed for filtered messages.
- `0ms` processing time is displayed as `0ms` instead of `-`.
