# Unified Deployment & 1Panel Optimization

## Context
User requests optimization of the deployment flow, specifically for 1Panel support and unifying the startup scripts.
Currently, there are multiple start scripts (`docker_start.sh`, `docker_start_optimized.sh`) and a `deploy.sh`.
`Dockerfile` appears to be missing or implicitly handled (which is bad practice for explicit 1Panel support).

## Objective
1.  **Unify Startup Scripts**: Merge `docker_start.sh` and `docker_start_optimized.sh` into a single `scripts/ops/entrypoint.sh`.
2.  **Explicit Dockerfile**: Create a robust `Dockerfile` in the root (or `scripts/ops/` if preferred, but root is standard) that uses the entrypoint.
3.  **1Panel Compatibility**:
    - Ensure `docker-compose.yml` uses the explicit `build` context or image.
    - Validate relative paths.
    - 1Panel often struggles with `build: .` if not running locally. We will keep `build: .` but ensure `Dockerfile` exists.
    - Add `restart: always`.
4.  **Simplify**: Remove obsolete scripts.

## Task List
- [x] Create `scripts/ops/entrypoint.sh` logic (merging optimized and normal) <!-- id: 0 -->
- [x] Create/Restore `Dockerfile` <!-- id: 1 -->
- [x] Update `docker-compose.yml` <!-- id: 2 -->
- [x] Update `scripts/ops/deploy.sh` to use the new structure (deleted as redundant) <!-- id: 3 -->
- [x] Cleanup old scripts (`docker_start.sh`, `docker_start_optimized.sh`) <!-- id: 4 -->
- [x] Verify 1Panel compatibility (simulation) <!-- id: 5 -->
