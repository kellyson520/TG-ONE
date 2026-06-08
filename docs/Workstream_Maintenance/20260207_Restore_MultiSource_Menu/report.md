# Bug Fix Report: Restore Missing Multi-Source Management Menu
## Issue Description
User reported "Multi-source Management" (我的多源管理) was missing from the new menu system.

## Root Cause
The `multi_source_management` feature was implemented in `rules_menu.py` but was not exposed in the `MenuController`, nor was the entry point button added to the `Forward Hub` in `new_menu_callback.py` and `main_menu_renderer.py`.

## Fix Implementation
1.  **Exposed Entry Point**: Added `show_multi_source_management`, `show_multi_source_detail`, `show_rule_status`, and `show_sync_config` methods to `controllers/menu_controller.py`.
2.  **Added Button**: Added "🔗 多源管理" button to the `render_forward_hub` method in `ui/renderers/main_menu_renderer.py`.
3.  **Wired Callbacks**: Added handlers for `multi_source_management`, `manage_multi_source`, `rule_status`, and `sync_config` actions in `handlers/button/callback/new_menu_callback.py`.

## Verification
- User can now access "Multi-source Management" from the Forward Hub.
- The workflow correctly navigates to the multi-source rule list and details.

## Status
✅ Complete
