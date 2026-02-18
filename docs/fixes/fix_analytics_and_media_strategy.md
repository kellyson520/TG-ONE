# Implementation Plan - Fix Analytics Service, Media Strategy and History Navigation

This plan outlines the fixes applied to resolve `AttributeError` in `analytics_service`, implement the missing `media_filter_config` action, and correct the navigation flow in history task selection.

## User Review Required

> [!IMPORTANT]
> verify that `ForwardRule` model should use `description` instead of `name`. The `name` attribute does not exist in the current schema.

- **Complexity**: 2 (Routine fixes)
- **Risk**: Low (Targeted fixes)

## Proposed Changes

### Fix 1: Resolve AttributeError in Analytics Service

**File**: `services/analytics_service.py`
**Description**: 
- Replaced `fr.name` with `fr.description` in `get_detailed_analytics`.
- The `ForwardRule` model definition confirms `name` attribute is missing.
- Fallback logic remains: `fr.description or f"Rule {rs.rule_id}"`.

### Fix 2: Implement Missing Media Strategy Handler

**File**: `handlers/button/strategies/media.py`
**Description**:
- Added `media_filter_config` to `MediaMenuStrategy.ACTIONS`.
- Implemented handler logic to bypass `rule_id` check for this global action.
- Directly calls `menu_controller.container.media_controller.show_media_filter_config(event)`.

### Fix 3: Correct History Task Navigation

**File**: `handlers/button/strategies/history.py`
**Description**:
- Changed the post-selection logic on `select_history_rule` / `select_task`.
- Instead of returning to the main history hub (`show_history_messages`), it now proceeds to the task configuration/start page (`menu_controller.show_history_task_actions`).
- This resolves the user issue where selecting a rule would loop back to the start.

## Verification Plan

### Automated Tests
- Run `pytest tests/unit/services/test_analytics_service.py` if available (or skip if not applicable).
- Manually verify the specific button click in UI if possible (simulated).
- Check logs for absence of `AttributeError` and `[UNMATCHED]` warnings.

### Manual Verification
1.  **Analytics**: Check "Detailed Analytics" or similar page in Web UI/Bot to ensure no 500/Crash.
2.  **Media Filter**: Click "Media Type Settings" in History Hub (or wherever `media_filter_config` is triggered) and ensure the menu opens.
3.  **History Task**: In "History Completion Center", select a rule. Confirm it navigates to "Task Configuration" page (with "Start Execution" button) instead of returning to the Center.
