# Bugfix Report: Fix Unmatched History Actions

## Summary
Resolved the issue where `select_history_task` and `select_task` actions were unmatched by the button strategy registry. These actions are used in the Legacy `HistoryModule` UI but were not included in the modern `HistoryMenuStrategy` action set.

## Changes
- **File**: `handlers/button/strategies/history.py`
    - Added `select_history_task` and `select_task` to the `ACTIONS` set.
    - Updated the `handle` method to process these actions as aliases for `history_task_selector` and `select_history_rule` respectively.

## Verification Result
- Syntax check: Passed.
- Code review: Verified that `select_history_task` in `HistoryModule` now correctly triggers the task selector, and `select_task` correctly handles rule selection.
- Alignment: Improved consistency between legacy UI modules and modern strategy-pattern handlers.

## Status
✅ Fixed.
