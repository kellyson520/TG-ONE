# Task: Fix ModuleNotFoundError for session_callback

## Problem
`controllers/domain/admin_controller.py` attempts to import `callback_session_management` from `handlers.button.callback.session_callback`, but this module does not exist.

## Plan
1. [x] Fix `AdminController.show_session_management` in `controllers/domain/admin_controller.py` to use `new_menu_system`.
2. [x] Remove duplicate `show_session_management` from `controllers/menu_controller.py`.
3. [x] Verify that session management menu can be displayed without errors.

## Execution
- **Phase 1: Fix AdminController**
  - Path: `controllers/domain/admin_controller.py`
  - Change: Update `show_session_management` method.
- **Phase 2: Cleanup MenuController**
  - Path: `controllers/menu_controller.py`
  - Change: Remove redundant `show_session_management` implementation.
