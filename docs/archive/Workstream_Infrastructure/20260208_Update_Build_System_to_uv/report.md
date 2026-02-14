# Update Build System to uv Report

## Summary
Successfully updated the build system and dependency management to use `uv` across the entire project, including Docker, local development scripts, and the update service.

## Key Changes

### Docker Integration
### Docker Integration
- **Updated `Dockerfile`**: Used `COPY --from=ghcr.io/astral-sh/uv:0.10.0` to install specific `uv` version, ensuring reproducible builds.
- **Optimization**: Switched to `uv` for significantly faster virtualenv creation and dependency resolution.

### Local Development & Scripts
- **Updated `scripts/ops/entrypoint.sh`**: Replaced complex `pip install` + manual uninstall logic with `uv pip sync`, which ensures exact dependency alignment (install/uninstall) in one fast step.
- **Updated `services/update_service.py`**: Changed `_sync_dependencies` to use `uv` for hot updates.
- **Updated `scripts/ops/sync_dependencies.py`**: Rewrote to use `uv pip install` directly for better reliability.
- **Documentation**: Added `docs/setup_guide.md` and updated `README.md` (root and `web_admin`) to recommend `uv`.
- **Local CI**: Updated `local_ci.py` to suggest `uv pip install` for missing packages.

## Verification
- **Code Review**: Verified all changes replace `pip install` with equivalent `uv` commands.
- **Docker**: The Docker build process should now be faster due to `uv` caching and resolution speed.
- **Consistency**: All installation paths (Docker, Update Service, Manual Scripts) now use `uv`.

## Next Steps
- Developers should install `uv` locally: `pip install uv`.
- Future dependency updates will be faster.
