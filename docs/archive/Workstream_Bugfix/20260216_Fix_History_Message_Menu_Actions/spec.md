# Bugfix: Fix Missing/Unmatched History Message Menu Actions

## Background
Audit of the "History Message" processing menu revealed several orphaned actions that were not registered in the new Strategy-based button system. This prevented users from configuring filters (Media types, duration, limit) in History mode.

## Diagnosis
The following actions in `HistoryModule` (legacy) were found to be unmatched in `HistoryMenuStrategy` or `SettingsMenuStrategy`:
- `history_message_filter`
- `history_filter_media_types`
- `history_filter_media_duration`
- `history_message_limit`
- `set_history_limit`
- `custom_history_limit`
- `set_history_delay`

Some filter toggles like `history_toggle_image` are correctly matched by `SettingsMenuStrategy`, but orphans like `history_message_filter` are stuck.

## Solution Plan
1. **Update `HistoryMenuStrategy`**:
    - Add the missing actions to `ACTIONS`.
    - Implement the `handle` logic to call `history_module` rendering or service updates.
2. **Implement `set_history_limit` logic**:
    - Update `settings.HISTORY_MESSAGE_LIMIT`.
    - Provide user feedback and return to the menu.
3. **Verify**:
    - Use `tests/simulate_history_actions.py` to ensure 100% matching.

## Note on Architecture
`HistoryMenuStrategy` acts as a proxy to `HistoryModule` during this migration phase to ensure UI continuity while complying with the Strategy Pattern.
