# Bugfix Report: Fix Missing History Message Menu Actions

## Summary
Resolved the issue where history message filtering and limit settings were inaccessible in the Bot menu due to missing action registrations in the new Strategy Pattern system. 

## Changes
- **File**: `handlers/button/strategies/history.py`
    - Added the following actions to `HistoryMenuStrategy.ACTIONS`:
        - `history_message_filter`
        - `history_filter_media_types`
        - `history_filter_media_duration`
        - `history_message_limit`
        - `set_history_limit`
        - `custom_history_limit`
        - `set_history_delay`
    - Implemented handling logic for these actions:
        - Filter menu actions now correctly call the corresponding `history_module` functions.
        - `set_history_limit` updates the global `settings.HISTORY_MESSAGE_LIMIT`.
        - `set_history_delay` is now correctly handled (previously only `set_delay` was present).

## Verification Result
- **Simulated Test**: Ran `tests/simulate_history_actions.py` which covers all actions used in the `HistoryModule` UI.
- **Result**: `All actions successfully matched!`
- **Architecture**: Complies with the Strategy Pattern and PSB engineering protocol.

## Status
✅ Fixed.
