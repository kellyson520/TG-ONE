# Specification: Session Management Fix

## Background
The system encountered a `ModuleNotFoundError` when users tried to access the "Session Management" menu. This was due to an incorrect import path in the `AdminController`.

## Proposed Changes

### 1. `controllers/domain/admin_controller.py`
The `show_session_management` method currently uses:
```python
from handlers.button.callback.session_callback import callback_session_management
await callback_session_management(event, None, None, None, None)
```
This should be changed to use the unified `new_menu_system` proxy:
```python
from handlers.button.new_menu_system import new_menu_system
await new_menu_system.show_session_management(event)
```

### 2. `controllers/menu_controller.py`
The file has two definitions of `show_session_management`.
- Definition 1 (Lines 145-153): Manual rendering.
- Definition 2 (Lines 591-593): Delegation to `AdminController`.
We should keep only Definition 2 to maintain the architecture of delegating domain tasks to domain-specific controllers.

## Verification
1. Ensure the application starts without import errors.
2. If possible, trigger the `session_management` action and verify the menu displays correctly.
