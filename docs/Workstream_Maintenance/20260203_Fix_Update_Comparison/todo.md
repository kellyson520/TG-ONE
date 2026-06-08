# Fix Update Comparison Logic

## 背景 (Context)
用户反馈更新系统在代码一致的情况下仍提示有更新。经过分析，原因可能包括：
1. Git 比较逻辑过于简单（仅使用 `!=`），未区分“落后”与“领先/偏移”。
2. 安全交叉验证中的 GitHub API URL 拼接错误（多了 `github.com/` 前缀）。
3. HTTP 模式下状态文件中的 `current_version` 记录不一致。

## 待办清单 (Checklist)

### Phase 1: 逻辑修正
- [x] 修正 `UpdateService` 中的 `OFFICIAL_REPO` 定义，移除域名前缀。
- [x] 优化 `_check_via_git` 比较逻辑，使用 `git rev-list HEAD..origin/BRANCH` 检测是否真正“落后”。
- [x] 优化 `_check_via_http` 比较逻辑，确保 `state` 文件中的版本记录逻辑闭环。
- [x] 改进 `_perform_git_update`，在更新成功后记录真实的 SHA 而非显示字符串。

### Phase 2: 验证与清理
- [x] 验证 `check_for_updates` 在代码一致时返回 `False`。
- [x] 验证 `_cross_verify_sha` 的 API 调用是否正确。
- [x] 生成任务报告。
