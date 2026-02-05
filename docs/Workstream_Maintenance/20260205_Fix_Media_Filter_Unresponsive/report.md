# Report: Media Filter Unresponsive Fix

## Summary
Fixed the issue where clicking media type filter buttons (Image, Video, etc.) in the global setting menu resulted in no response.

## Changes
- **File**: `handlers/button/callback/new_menu_callback.py`
  - Added a handler for the `toggle_media_type` action in `callback_new_menu_handler`.
  - This allows the generic `new_menu:toggle_media_type:{type}` callback data to be correctly dispatched to `handle_toggle_media_type`.

## Verification Results
- **Code Audit**: Verified all other buttons in `FilterMenu` (Size, Duration, Extension) have corresponding handlers in `new_menu_callback.py`.
- **Static Analysis**: `python -m py_compile` passed for the modified file.
- **Functional Check**: Compared with `HistoryModule` implementation, confirming that global settings now follow the same robust pattern for media type toggling.

## Impact
- Users can now correctly toggle global media type filters from the bot menu.
- Improved consistency between global settings and history task settings.
