# Test Plan: Update System & Guardian Robustness

## 1. Unit Tests (Embedded Logic)
Test the Python snippets used inside `entrypoint.sh` for dependency alignment.
- **Goal**: Ensure the parser doesn't uninstall critical tools or crash on complex `requirements.txt` formats.
- **Scenarios**:
    - `pkg==1.0`
    - `pkg>=2.0,<3.0`
    - `pkg[extra]`
    - `pkg; python_version < "3.8"`
    - `# comment lines`
    - Blank lines

## 2. Integration Tests (Backup Rotation)
Test the `_rotate_backups` method in `UpdateService`.
- **Goal**: Verify files are deleted based on time, not just name, and the limit is respected.

## 3. Simulation Tests (Shell Logic)
Since we are on Windows, we'll use a Python test to simulate the `entrypoint.sh` flow.
- **Goal**: Verify the "Loop -> Check -> Install -> Run" sequence conceptually.

## 4. Edge Cases
- **Git failure during update**: Ensure the lock file is handled and rollback is triggered.
- **Pip failure**: Ensure the guardian doesn't enter an infinite retry loop without sleep/cooling.
- **Empty requirements.txt**: Should not crash or uninstall everything.
- **Disk Full**: (Note: hard to simulate, but ensure exception handling in Python).
