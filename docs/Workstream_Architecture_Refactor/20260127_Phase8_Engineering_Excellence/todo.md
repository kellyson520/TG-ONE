# Phase 8: Engineering Excellence & Compliance

## Context
Goal: Perfect infrastructure, ensure long-term maintainability.
Parent: [Main Todo](../todo.md)

## Checklist

### 1. Standardization & Compliance (P1)
- [ ] **Configuration Audit**: Clear `os.getenv`, force `core.config.settings`.
- [ ] **ORM Leak Audit**: Script to check Service return values.
- [ ] **Dead Code**: Scan with `vulture`.
- [ ] **Type Hints**: Core modules 100% coverage.

### 2. Testing Engineering 2.0 (P1)
- [ ] **Arch Guard**: Script to enforce layering (No Service -> UI, No Infra -> Domain direct).
- [ ] **Performance Gate**: Resource checks (No stress test).

### 3. Deployment & Optimization (P2)
- [ ] **Smart Sleep**: Idle circuit breaker.
- [ ] **SQLite Optimization**: WAL check.

### 4. Verification
- [ ] `check_completeness` script.
- [ ] Benchmark performance before and after refactoring.
