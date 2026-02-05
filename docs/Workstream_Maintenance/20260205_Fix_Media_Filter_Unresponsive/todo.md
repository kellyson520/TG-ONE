# Task: Fix Media Filter Unresponsive

## Background
User reported that the media type filter in the menu bot is unresponsive.

## Analysis
- `FilterMenu.show_media_types` uses callback data `new_menu:toggle_media_type:{type}`.
- `new_menu_callback.py` is missing the handler for `toggle_media_type`.
- Other similar handlers like `history_toggle_image` exist but don't cover global settings.

## Todo
- [x] Add `toggle_media_type` handler to `callback_new_menu_handler` in `new_menu_callback.py`.
- [x] Verify other buttons in `FilterMenu` are correctly handled.
- [x] Final verification and consolidation of callback handlers.
- [x] Fix `RadixRouter` to support multi-part greedy matching (to prevent future "handler empty" errors).

## Status
- **Phase**: Report
- **Status**: Reinforcement complete. Fixed core router logic for greedy matching of sub-system callbacks. Pushing again for deployment.
