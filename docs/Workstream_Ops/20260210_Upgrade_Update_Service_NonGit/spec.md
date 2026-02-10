# 升级服务支持非 Git 环境技术方案 (Technical Spec)

## 背景 (Context)
系统原有的更新机制深度绑定 Git (git pull / git reset)。在无 Git 环境（如轻量化 Docker 容器）下，更新会因找不到 git 命令而彻底失效。

## 目标 (Goals)
1. 使系统在缺失 `git` 命令时仍能完成代码更新。
2. 确保更新流程在非 Git 环境下的可靠性（备份、增量覆盖、重启校验）。
3. 统一 CLI 和 Web 端在不同环境下的展示效果。

## 核心设计 (Design)

### 1. 双层环境检测 (Double-Layer Detection)
- **Python 层**: 通过 `shutil.which("git")` 检测安装状态，通过 `.git` 文件夹存在性检测仓库状态。
- **Bash 层**: 通过 `command -v git` 检测命令可用性。

### 2. 更新原子性保障 (Atomicity)
- **Git 环境**: 维持原有的 `git fetch + reset --hard`，这是最可靠的原子更新方式。
- **非 Git 环境**:
    - **逻辑迁移**: 将代码下载与解压逻辑从 Shell 脚本前置到 Python 脚本。
    - **预下载 (Pre-download)**: `UpdateService.trigger_update` 会先行调用 `_perform_http_update` 下载并覆盖代码，但不立即重启。
    - **守护进程接管**: Python 退出并返回 Exit Code 10。
    - **物理快照**: `entrypoint.sh` 检测到 Git 缺失时，跳过 git 指令，但依然执行 `tar` 物理备份并将当前状态持久化，然后重启应用。

### 3. 支持版本指定 (Version Support)
- `_perform_http_update` 现在支持根据传入的版本号猜测 GitHub ZIP URL：
    - 若为 7 位或 40 位 16 进制字符串 -> 判定为 Commit SHA 模式。
    - 否则 -> 判定为 Branch/Tag 模式。

## 实施步骤 (Implementation Steps)

### Step 1: 守护进程改造 (entrypoint.sh)
- 为所有 `git` 指令增加 `command -v git` 前置逻辑。
- 优化 `PREV_SHA` 的获取，若非 git 环境则留空，不阻塞流程。

### Step 2: 核心服务升级 (UpdateService.py)
- `trigger_update`: 增加环境判定。非 Git 环境下同步调用 HTTP 下载。
- `perform_update`: 暴露 `target_version` 参数供手动升级使用。
- `_perform_http_update`: 实现多模式 URL 解析（Branch vs SHA）。
- `get_update_history`: 非 Git 环境下回退显示 `state` 文件中的版本。

### Step 3: 工具链适配 (manage_update.py)
- 更新文本描述，区分 Git/Standard 模式。
- 增强显示鲁棒性。

## 验证计划 (Verification)
1. **模拟环境测试**: 在临时容器或删除 PATH 中的 git 路径后运行。
2. **回滚验证**: 故意破坏代码导致启动失败，验证 `entrypoint.sh` 是否能通过物理备份 (`tar.gz`) 完成回滚。
