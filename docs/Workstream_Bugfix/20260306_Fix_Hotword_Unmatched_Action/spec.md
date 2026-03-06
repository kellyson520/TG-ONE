# Task: Fix [UNMATCHED] Action 'hotword_global_refresh'

## 1. Problem Analysis
- **Symptom**: `[UNMATCHED] Action 'hotword_global_refresh' has been unmatched 1 times` error in logs.
- **Location**: `handlers.button.strategies.registry`
- **Root Cause**: The system is migrating to a Strategy Pattern for callback handling. Some entry points (like `handle_new_menu_callback` or updated module handlers) call `MenuHandlerRegistry.dispatch`. Since `hotword_global_refresh` is not registered in any strategy, it fails the match and logs an error, even if a legacy handler eventually catches it.

## 2. Proposed Solution
Migrate Hotword callback handling to the Strategy Pattern.
1. Create `handlers/button/strategies/hotword.py`.
2. Define `HotwordMenuStrategy` and register it using `@MenuHandlerRegistry.register`.
3. Move logic from `handle_hotword_callback` to the new strategy.
4. Update `handlers/button/callback/modules/hotword_callback.py` to be a thin wrapper around the registry.

## 3. Implementation Plan

### Phase 1: Strategy Implementation
- Create `handlers/button/strategies/hotword.py`.
- Handle actions: `hotword_global_refresh`, `hotword_main`, `hotword_search_prompt`, `hotword_view`.

### Phase 2: Registration & Integration
- Ensure `hotword_global_refresh` is in `HIGH_FREQUENCY_ACTIONS` in `registry.py` for performance tracking.
- Update `handle_hotword_callback` in `modules/hotword_callback.py` to call `MenuHandlerRegistry.dispatch`.

### Phase 3: Verification
- Run static analysis (`py_compile`).
- (Optional) Run related tests.
