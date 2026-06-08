# Fix Update Comparison Logic Report

## Summary
修复了系统在本地代码与云端一致时仍误提示“有更新”的问题。优化了 Git 更新检测机制，并修正了 GitHub API 的安全校验路径。

## Changes
1.  **UpdateService (`services/update_service.py`)**:
    *   **Git 比较逻辑升级**: 弃用了简单的 `local_id != remot_id` 判断。改为使用 `git rev-list HEAD..origin/BRANCH --count`。现在系统只有在本地真正落后于远程（即本地缺少远程仓库的新提交）时，才会提示有更新。如果本地领先或完全同步，则不再误报。
    *   **API 路径纠错**: 修正了 `OFFICIAL_REPO` 的定义。此前拼接出的 GitHub API URL 包含重复的域名（如 `repos/github.com/...`），导致安全交叉验证始终 404 并跳过。现已修正为标准的 `owner/repo` 格式。
    *   **状态持久化优化**: 在 Git 更新完成后，现在会将远程仓库的真实 SHA 写入 `update_state.json` 的 `current_version` 字段。这确保了在 Git 命令偶尔失效回退到 HTTP 检查模式时，版本比对逻辑依然能够闭环，不会产生误报。
+    *   **关键 Bug 修复**: 修复了 `_perform_git_update` 中 `remot_id` 变量未定义导致的更新执行崩溃问题。

2.  **安全性增强**:
    *   修正了 `_cross_verify_sha` 的调用链，现在能够正确通过 GitHub API 验证远程 SHA 是否属于官方主分支，防止潜在的 DNS 劫持或 `.git/config` 劫持。

## Verification
*   **SHA 比对验证**: 手动执行 `git rev-parse HEAD` 和 `git rev-parse origin/main` 确认一致。
*   **落后数验证**: 执行 `git rev-list HEAD..origin/main --count` 结果为 0，符合预期。
*   **API 连通性**: 测试 `https://api.github.com/repos/kellyson520/TG-ONE/commits/main` 返回 200 及匹配的 SHA。

## Conclusion
更新系统的检测准确度大幅提升，成功解决了用户反馈的“一模一样还是显示可以更新”的问题。
