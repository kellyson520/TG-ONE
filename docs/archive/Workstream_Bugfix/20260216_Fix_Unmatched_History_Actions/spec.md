# Bugfix: Fix Unmatched History Actions

## Background
User reported `[UNMATCHED] Action 'select_history_task' has been unmatched` in `handlers.button.strategies.registry`.
Investigation revealed that several history-related actions used in the UI are not registered in the `HistoryMenuStrategy`.

## Diagnosis
- `select_history_task`: Used in `HistoryModule.show_history_messages` but missing from `HistoryMenuStrategy`.
- `select_task`: Used in `HistoryModule.show_history_task_selector` but missing from `HistoryMenuStrategy`.
- `HistoryMenuStrategy` uses `history_task_selector` and `select_history_rule` which are functionally equivalent but named differently.

## Solution Plan
1. Update `handlers/button/strategies/history.py`:
    - Add `select_history_task` to `ACTIONS`.
    - Add `select_task` to `ACTIONS`.
    - Update `handle` method to support these new action aliases.
2. Verify the fix (simulated as I cannot easily click buttons in real-time, but code review and potentially a unit test).

## Risks
- Minor: naming confusion, but using aliases solves this without breaking existing UI.
