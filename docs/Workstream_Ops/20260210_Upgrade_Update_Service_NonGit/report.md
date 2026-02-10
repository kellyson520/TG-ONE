# 升级服务支持非 Git 环境任务报告 (Report)

## 任务概况 (Summary)
成功升级了系统的自动更新与自动回退服务，使其能够在完全缺失 `git` 环境（如精简 Docker 镜像）下正常工作。通过 Python 层的预下载机制与 Shell 层的安全降级策略，实现了更新流程的解耦与增强。

## 核心变更 (Changes)

### 1. 守护进程增强 (scripts/ops/entrypoint.sh)
- **Git 命令防护**: 在所有 `git fetch`, `git reset`, `git rev-parse` 指令前增加了 `command -v git` 校验。
- **降级逻辑**: 若环境无 Git，Shell 脚本将跳过代码拉取环节，直接通过 Python 层的状态锁决定是否重启。
- **回滚增强**: 物理备份还原 (`tar.gz`) 现已成为非 Git 环境下的主选回滚方式，替代 `git reset`。

### 2. 核心服务重构 (services/update_service.py)
- **手动更新适配**: `trigger_update` 方法现在会检测环境。若为非 Git 环境，会立即通过 HTTP 下载指定的 ZIP 更新包并执行增量覆盖，然后再退出进程。
- **HTTP 更新增强**: `_perform_http_update` 现在支持传入 commit SHA。系统会自动识别 SHA 或 Branch/Tag 并生成对应的 GitHub 下载地址。
- **版本展示修复**: 当处于非 Git 环境时，版本信息获取逻辑会自动回退至 `data/update_state.json` 中的记录，确保 Web UI 不显示“未知”或报错。

### 3. 管理工具适配 (manage_update.py)
- **模式感知**: 工具现在会显式标识当前是 Git 模式还是 Standard (Non-Git) 模式。
- **文案优化**: 明确告知用户回滚的执行路径（Git vs 物理备份）。

### 4. 版本校验与显示优化 (Phase 5)
- **状态文件归口**: 废弃了根目录冗余的 `VERSION` 文件，统一将版本指纹（SHA）持久化至 `data/update_state.json`。
- **全链路 SHA 校验**: 修复了 `_cross_verify_sha` 在手动指定版本时的校验失败问题，现在支持对特定 SHA/Tag 进行远程指纹比对。
- **版本解析能力**: `_perform_http_update` 会在更新完成后尝试通过 GitHub API 解析 branch 名对应的真实 SHA，并将其持久化，确保后续对比的精确度。
- **历史记录修复**: 修正了 `get_update_history` 在无 Git 环境下可能显示为空的问题，现在能够通过状态文件正确显示当前运行版本。

## 验证结论 (Verification)

### 1. 单元测试 (Passed)
- 运行 `pytest tests/unit/services/test_update_service_industrial.py`。
- **结果**: 17 个测试用例全部通过（100%）。
- **覆盖点**: 双层状态机迁移、DB 原子备份、手动更新触发、迁移失败回滚、损坏锁处理等。

### 2. 鲁棒性验证
- 通过 Mock 模拟了 `shutil.which("git")` 返回 `None` 的场景，确认 `trigger_update` 正确触发了 HTTP 下载流程。
- 验证了 `alembic` 目录缺失时的非阻塞提示，确保系统能够正常启动。

## 手动操作指南 (Manual)
- **手动升级**: `python manage_update.py upgrade [branch_or_sha]`
- **手动回滚**: `python manage_update.py rollback`
- **查看状态**: `python manage_update.py status`
