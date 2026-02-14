# Update Build System to uv

## Context
Replace `pip` with `uv` for faster and more reliable dependency management. The goal is to modernize the build process.

## Checklist

### Phase 1: Docker Integration
- [x] Update `Dockerfile` to install `uv`
- [x] Replace `pip install` with `uv pip install --system` in `Dockerfile`
- [x] Verify Docker build

### Phase 2: Local Development and Scripts
- [x] Update `scripts/ops/entrypoint.sh`
- [x] Update `README.md` to reflect `uv` usage
- [x] Scan for other `pip` usages and replace where appropriate

### Phase 3: Verification
- [x] Verify application starts correctly with new build
- [x] Verify all dependencies are installed
