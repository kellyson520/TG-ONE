# Phase 8: Engineering Excellence & Compliance

## Context
Goal: Perfect infrastructure, ensure long-term maintainability.
Parent: [Main Todo](../todo.md)

## Checklist

### 1. Standardization & Compliance (P1)
- [ ] **Configuration Audit**: Clear `os.getenv`, force `core.config.settings` (In progress: 50+ usages left).
- [x] **ORM Leak Audit**: Script to check Service return values (Done: `scripts/orm_leak_scanner.py`).
- [ ] **Dead Code**: Scan with `vulture`.
- [ ] **Type Hints**: Core modules 100% coverage (In progress).

### 2. Testing Engineering 2.0 (P1)
- [x] **Arch Guard**: Script to enforce layering (Done: `.agent/skills/local-ci/scripts/arch_guard.py`).
- [ ] **Performance Gate**: Resource checks (No stress test).

### 3. Deployment & Optimization (P2)
- [ ] **Smart Sleep**: Idle circuit breaker.
- [x] **SQLite Optimization**: WAL and Pool optimization implemented in `core/database.py`.

### 4. Verification
- [x] `docs/tree.md` updated.
- [ ] `check_completeness` script.
- [ ] Benchmark performance before and after refactoring.
