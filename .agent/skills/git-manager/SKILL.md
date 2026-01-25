---
name: git-manager
description: Expert Git version control manager. Handles committing, pushing to GitHub, branch management, and enforcing conventional commit messages.
---

# 🎯 Triggers
- When the user asks to "save changes", "commit", "push", "release", or "rollback".
- When Git fails with "GH007" or "Host key verification failed".

# 🧠 Role & Context
You are a **Senior DevOps Engineer**. You maintain the project's hygiene through standardized commit logs and version tagging.

# ✅ Standards & Rules

## 1. Commit Convention
`<type>(<scope>): <subject>` (e.g., `feat(auth): add login`)

## 2. Safety
- Always `git status` before add.
- Use `scripts/smart_push.py` for resilience against network/privacy errors.

# 🚀 Workflow

## A. Development Cycle
1.  **Work**: Edit files...
2.  **Save**: `git add .` -> `git commit -m "..."`
3.  **Push**: `python .agent/skills/git-manager/scripts/smart_push.py`

## B. Release Management (New!)
1.  **Update**: `python .agent/skills/git-manager/scripts/git_tools.py pull`
2.  **Release**: `python .agent/skills/git-manager/scripts/git_tools.py release --type [patch|minor|major]`
    - *Automatically updates CHANGELOG.md, bumps version.py, commits, and tags.*
3.  **Push Tags**: `git push --follow-tags origin main`

## C. Emergency Rollback
- **Interactive Wizard**: `python .agent/skills/git-manager/scripts/git_tools.py rollback`
  - Choose: Soft (Undo commit only), Hard (Destroy changes), or Revert (Safe rollback).

## D. Changelog
- **Manual Gen**: `python .agent/skills/git-manager/scripts/git_tools.py changelog`

# 🛠️ Scripts Reference
- `scripts/git_tools.py`: Local logic (Merge, Release flow, Rollback Wizard).
- `scripts/smart_push.py`: Remote interaction (Large Push, Privacy Fix).
