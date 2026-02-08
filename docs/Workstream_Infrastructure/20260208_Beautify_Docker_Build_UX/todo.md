# Beautify Docker Build UX

## Context
The user finds the current Docker build output "ugly". We aim to improve the visual experience of the build process by adding colored output, ASCII art headers, and structured logging within the `Dockerfile`.

## Strategy
1.  **Inject ANSI Colors**: Use `echo -e` with ANSI escape codes to print distinctive headers for build stages.
2.  **ASCII Art**: Add a project logo/banner at the start of the build.
3.  **Structured Steps**: Clearly visually separate major build steps (Dependencies, Venv, Copying).
4.  **Consistency**: Ensure the runtime entrypoint also shares this aesthetic.

## Checklist

### Phase 1: Builder Stage Enhancement
- [x] Add "Building..." ASCII Art banner.
- [x] Add colored status messages (`🔵 INFO`, `🟢 SUCCESS`) before major `RUN` instructions.
- [x] Configure `uv` for human-readable output where possible.

### Phase 2: Runtime Stage Enhancement
- [x] Add "Runtime" ASCII Art banner.
- [x] Add colored status messages for setup steps.

### Phase 3: Verification
- [x] Build the image and verify the output look and feel.
