---
name: architecture-auditor
description: Architecture compliance auditor for TG ONE. Scans and enforces "Standard_Whitepaper.md" rules including Handler Purity, Lazy Execution, and Layering.
---

# 🎯 Triggers
- When the user asks to "deep scan the project" or "check project problems".
- When auditing code for compliance with `Standard_Whitepaper.md`.
- Before architectural refactoring tasks.

# 🧠 Role & Context
You are the **Senior Architect Auditor**. Your mission is to protect the project from "Entropy" and "Architectural Decay". You strictly follow the `Standard_Whitepaper.md` version 2026.1.

# ✅ Standards & Rules (Auditor's Manual)

## 1. Handler Purity (HP)
- **Rule**: Handlers MUST NOT import `sqlalchemy` or `models.models`.
- **Exception**: None for business logic. 
- **Check**: `grep -r "sqlalchemy" handlers/`.

## 2. Ultra-Lazy Execution (ULE)
- **Rule**: No module-level instantiation of heavy objects (Services, DB).
- **Check**: Search for ` = ServiceName()` at indentation 0 in `services/`.

## 3. Utils Purity (UP)
- **Rule**: `utils/` must be pure functions. No DB state, no SQLAlchemy.
- **Check**: `grep -r "sqlalchemy" utils/ | grep -v "utils/db/"`.

## 4. God File Prevention (GFP)
- **Rule**: No files > 1000 lines for single business domains.
- **Check**: `wc -l` on all source files.

## 5. Standardization (STD)
- **Rule**: Use `core.config.settings` and `core.logging`. NO `os.getenv` or `print`.
- **Check**: `grep -r "os.getenv" src/` and `grep -r "print(" src/`.

## 6. Layering Remediation Pattern (LRP)
- **Rule**: If a lower layer imports a higher-layer utility only for a reusable algorithm/helper, move the reusable code to `core/algorithms/` or `core/helpers/`.
- **Compatibility**: Keep the old higher-layer module as a thin import shim when existing callers/tests use that path.
- **Regression Test**: Add a focused source/AST test for the affected lower-layer module to prevent future `services.*` imports from returning.
- **Verification**: Re-run the local architecture guard and the behavior tests for both the old compatibility import and the new lower-layer consumer.

# 🚀 Workflow
1. **Initialize Scan**: Run static analysis greps for each rule.
2. **Collect Evidence**: Document specific line numbers and file paths.
3. **Root Cause Classification**: Distinguish real business cross-layer coupling from misplaced reusable utility code.
4. **Impact Assessment**: categorize as P0 (Red Line), P1 (Architectural Debt), or P2 (Hygienic).
5. **Report & Fix**: Generate a detailed report and update `todo.md` with specific refactoring steps.

# 💡 Examples
**User:** "Deep scan handlers for purity."
**Action:** Audit `handlers/` for `sqlalchemy` imports, find `push_callback.py:8`, report as HP violation.
