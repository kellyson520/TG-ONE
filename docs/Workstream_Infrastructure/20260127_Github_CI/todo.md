# Task: Establish Standard Cloud CI (GitHub Actions)

## Context
Goal: Enable automated testing and quality checks on GitHub.
Parent: [Process](../process.md)

## Checklist

### Phase 1: Configuration (P0)
- [ ] **Workflow File**: Create `.github/workflows/ci.yml`.
    - [ ] Setup Python 3.10.
    - [ ] Install dependencies (cache pip).
    - [ ] Handle OS-specific deps (likely for PySide6/Qt if needed).
- [ ] **Quality Checks**:
    - [ ] Linting (flake8).
    - [ ] Formatting Check (black --check).

### Phase 2: Testing (P0)
- [ ] **Unit Tests**: Run `pytest -m unit`.
- [ ] **Integration Tests**: Run `pytest -m integration`.
- [ ] **Exclude Stress**: Ensure `stress` markers are skipped.

### Phase 3: Documentation
- [ ] Add Badge to README.md (optional).
