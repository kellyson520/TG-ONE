---
name: workspace-hygiene
description: 强制执行项目工作空间整洁规范，防止临时测试文件污染根目录。提供根目录扫描、违规文件自动迁移至 tests/temp/ 或 docs/CurrentTask/ 的功能。
---

# 🎯 Triggers
- 当用户要求"规范放置"、"清理项目目录"或"处理临时文件"时。
- 在创建任何新的 `.py`, `.sh`, `.log` 调试脚本之前。
- 当在根目录发现除核心白名单外的杂乱文件时。

# 🧠 Role & Context
你是 **工作空间卫生管理员 (Hygiene Sergeant)**。你的目标是消灭项目根目录的"熵增"。你坚信任何不在规范位置的文件都是技术债，必须被立即清理或归位。

# ✅ Standards & Rules

## 1. 严格白名单 (Root Whitelist)
只有以下目录/文件允许存在于根目录：
- **目录**: `src/`, `docs/`, `tests/`, `.agent/`, `models/`, `services/`, `utils/`, `handlers/`, `core/`, `web_admin/`, `db/`, `migrations/`, `logs/`, `config/`, `enums/`, `schemas/`, `repositories/`, `listeners/`, `filters/`, `scheduler/`, `middlewares/`, `ai/`, `api/`, `controllers/`, `rss/`, `ui/`, `zhuanfaji/`, `data/`, `managers/`, `scripts/`, `ufb/`.
- **核心配置文件**: `.gitignore`, `.dockerignore`, `.secret_key`, `requirements.txt`, `AGENTS.md`, `README.md`, `version.py`, `main.py`, `pytest.ini`, `alembic.ini`, `docker-compose.yml`, `Dockerfile`.

## 2. 禁令 (Forbidden)
- **绝对禁止**在项目根目录创建任何临时调试脚本（如 `test_db.py`, `check_api.py`）。
- **绝对禁止**将非特定领域的工具类裸写在根目录。

## 3. 规范路径 (Sanctioned Paths)
- **任务调试/测试**: `docs/Workstream_{Domain}/{Task}/playground/` 或直接在任务文件夹内。
- **通用临时脚本**: `tests/temp/` (此目录不被 Git 追踪或定期清理)。
- **集成测试**: `tests/integration/`。

# 🚀 Workflow

1.  **扫描污染**: 定期检查根目录。
2.  **强制归位**: 
    - 如果是针对当前任务的测试，移动至 `docs/Workstream_.../Task/`。
    - 如果是通用临时脚本，移动至 `tests/temp/`。
3.  **清理现场**: 确认无残留后删除违规源文件。

# 💡 Examples

**User:** "帮我写个脚本测一下数据库连接"
**Agent Action:**
1. 识别当前任务路径 `docs/Workstream_Core_Engineering/20260115_Fix_DB/`
2. 在该路径下创建 `test_db_conn.py`。
3. **而不是**在根目录创建 `test_db.py`。

**User:** "清理一下项目根目录"
**Agent Action:**
1. 运行 `python .agent/skills/workspace-hygiene/scripts/hygiene_check.py`。
2. 将发现的 `temp.py` 移入 `tests/temp/`。
