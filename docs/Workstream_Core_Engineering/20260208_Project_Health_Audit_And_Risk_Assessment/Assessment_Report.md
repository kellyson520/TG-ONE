# Project Health Audit & Risk Assessment Report

**Date**: 2026-02-08
**Auditor**: Antigravity (Architecture Auditor)
**Severity**: High (Requires Immediate Attention)

## 1. Executive Summary
The project suffers from **Critical Architectural Debt** centered around "God Files" in the Handler layer and pervasive violations of the Layered Architecture (Handlers accessing Database). While the Core Engineering hygiene is improving (Lazy Loading observed), the Presentation Layer (`handlers/`) is acting as a monolithic implementation bottleneck.

## 2. Critical Architecture Violations (P0)

### 2.1 Handler Purity Violations (DB Leakage)
**Rule**: Handlers MUST NOT access `container.db.session()` or `sqlalchemy` primitives.
**Status**: **FAILED**
**Evidence**:
- `handlers/button/callback/new_menu_callback.py`: Directly opens DB sessions (Line 252).
- `handlers/button/callback/push_callback.py`: Contains `sqlalchemy` imports.
- Multiple callback handlers follow this pattern, coupling UI logic with Data Access.

### 2.2 God File Anti-Patterns
**Rule**: No file should exceed 1000 lines (Single Responsibility Principle).
**Status**: **FAILED**
**Top Offenders**:
1.  `handlers/button/callback/new_menu_callback.py`: **2494 lines** (The "Menu Monolith")
2.  `handlers/button/callback/other_callback.py`: **2044 lines**
3.  `handlers/legacy_handlers.py`: **2423 lines** (Dead Code Risk)
4.  `handlers/commands/rule_commands.py`: **1428 lines**
5.  `services/session_service.py`: **1050 lines**

**Risk**: Any change to the Menu System requires navigating a 2500-line `if/elif/else` dispatch maze, significantly increasing bug probability and cognitive load.

### 2.3 Bare Except Usage (Silent Failures)
**Rule**: Never use `except:` without specifying exception type.
**Status**: **FAILED**
**Locations**:
- `handlers/button/callback/modules/rule_dedup_settings.py`
- `handlers/button/modules/picker_menu.py`
- `listeners/message_listener.py`
- `services/dedup/strategies/similarity.py`

## 3. Structural Consistency & Redundancy

### 3.1 Legacy Code Debris
- `tests/temp/archive/legacy_cleanup_20260128/legacy_handlers.py` (2423 lines) appears to be archived but adds noise.
- **Action**: Confirm if `handlers/legacy_handlers.py` (active path) exists. If so, it is a major redundancy.

### 3.2 "Utils" Identity Crisis
- The project lacks a root `utils/` directory, using `core/helpers/` instead.
- **Status**: **ACCEPTABLE** (as `core/helpers` is used consistently), but `utils` imports in some legacy code might break if not aliased.

## 4. Recommendations & Roadmap

### Phase 1: Surgical Extraction (Immediate)
1.  **Kill the God Handler**: Refactor `new_menu_callback.py` using the **Command Pattern** or **Strategy Pattern**. Map `action_data` string keys to independent Handler Classes.
2.  **Enforce DB Ban**: Move all `async with container.db.session():` blocks from Handlers to corresponding `Services`.

### Phase 2: Code Hygiene
1.  **Linting Guard**: Add a `pre-commit` hook or CI check to reject `except:` (bare except).
2.  **Dead Code Removal**: Archive or Delete `legacy_handlers.py` if confirmed unused.

### Phase 3: Service Slicing
1.  **SessionService Split**: Decompose `session_service.py` into `SessionCleanupService`, `SessionQueryService`, and `SessiondedupService`.

## 5. Conclusion
The system functions but is "brittle" in the Frontend/Handler layer. Features are easy to break because they are entangled in massive files. **Refactoring `new_menu_callback.py` is the highest ROI engineering task available.**
