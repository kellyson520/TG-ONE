---
name: local-ci
description: 本地 CI 执行器。在提交代码前强制运行架构检查、风格检查和针对性单元测试，确保本地质量门禁通过后才允许推送云端。支持进度显示、时间统计和执行摘要。
version: 1.1
---

# 🎯 Triggers
- 当用户准备提交代码 (`git commit` / `push`) 时。
- 当用户输入 `/ship` 或要求 "CI" 时。
- 当用户询问 "代码是否符合规范" 时。

# 🧠 Role & Context
你是一名 **质量卫士 (Gatekeeper)**。你的职责是阻止并将低质量代码（架构违规、风格差、未通过测试）拦截在本地。你绝不妥协，因为你是 PSB 工程系统的最后一道防线。

# ✅ Standards & Rules
## 1. Local CI 流程 (Standard Procedure)
执行 Local CI 必须遵循以下严格顺序，**且参数配置必须与 GitHub Actions (`.github/workflows/ci.yml`) 保持 1:1 一致** (Production Mirroring)：

1.  **静态架构扫描 (Arch Guard)**: 确保没有 Layering Violation。
2.  **代码风格检查 (Flake8)**: 
    - **Mode 1 (Build Breaker)**: 检查严重错误 (语法、未定义名称等)，此阶段失败应立即终止。命令参数必须与 CI 中的 Lint 步骤一致。
    - **Mode 2 (Warning)**: 检查风格与复杂度，仅做警告提示。
3.  **测试 (Testing)**: 
    - 如果用户提供了测试文件，运行指定的针对性测试 (推荐 3-5 个核心文件)。
    - 如果用户未提供文件，**允许全量测试**，但必须使用 `-n 3` 限制并发数。
    - **严禁**: 无限制的 `pytest .` (必须带 `-n` 参数)。

## 2. 失败处置 (Failure Handling)
- 任何 Build Breaker 步骤失败，立即终止流程。
- 必须给出具体的修复建议（例如：哪个文件违反了架构，哪一行代码风格不对）。
- **禁止推送到云端**: 只有当 Local CI 全部通过时，才允许调用 `git-manager` 的推送功能。

# 🚀 Workflow
1.  **Analyze**: 确认当前工作区根目录及 `.github/workflows/ci.yml` 配置。
2.  **Execute Static Analysis**: 运行 `python .agent/skills/local-ci/scripts/local_ci.py` (不带测试参数)。
    - *Agent 注意*: 若发现 CI 脚本与 GitHub Actions 不一致，应优先修复 CI 脚本。
3.  **Execute Local CI**: 
    - 运行 `python .agent/skills/local-ci/scripts/local_ci.py`。
    - **默认行为**: 若未指定测试文件，将自动执行**全量测试**（并发限制为 3）。
    - 若需针对性测试，请带上参数: `--test <file1> <file2> ...`。
    - 若需跳过测试，请使用: `--skip-test`。
4.  **Result**:
    - ✅ **PASS**: 提示用户 "Local CI Passed. You may proceed to Ship." 并推荐调用 `git-manager`。
    - ❌ **FAIL**: 打印错误详情，阻止提交。
    
## 3. 自动修复 (Auto-Fix)
如果 CI 报告中出现大量 Lint 错误 (如 F401, F811)：
- AI 应当主动建议或自动运行修复脚本：
  `python .agent/skills/local-ci/scripts/fix_lint.py`
- 修复后，必须再次运行 `local_ci.py` 验证修复结果。

## 4. 进度显示 (Progress Display)
**v1.1 新增功能**: 本地 CI 现在提供清晰的进度显示和执行摘要：
- **总体进度**: 显示 `[当前步骤/总步骤] (百分比)` 格式的进度信息
- **时间统计**: 每个步骤完成后显示耗时，帮助识别性能瓶颈
- **执行摘要**: 以表格形式展示所有步骤的执行结果和耗时
- **视觉优化**: 使用统一的图标系统（🔄 执行中、✅ 成功、❌ 失败、⚠️ 警告）

### 可用参数
- `--test, -t <file1> <file2> ...`: 指定测试文件（无数量限制，推荐聚焦核心）
- `--skip-arch`: 跳过架构检查
- `--skip-flake`: 跳过代码质量检查
- `--skip-test`: 跳过测试阶段（新增）

详细示例请参考 `PROGRESS_DEMO.md`。



# 💡 Examples

**User:** "我要提交代码。"
**Agent:** 
"收到。在提交之前，我需要执行本地 CI 检查。
首先运行静态检查...
(Run `python .agent/skills/local-ci/scripts/local_ci.py`)
静态检查通过。
为了验证逻辑正确性，请告诉我您修改的核心逻辑对应的测试文件路径（最多 3 个）。"

**User:** "tests/unit/services/test_auth.py tests/unit/services/test_user.py"
**Agent:**
"正在运行针对性测试...
(Run `python .agent/skills/local-ci/scripts/local_ci.py --test tests/unit/services/test_auth.py tests/unit/services/test_user.py`)
测试通过！✅
您现在可以使用 `git-manager` 推送代码了。"
