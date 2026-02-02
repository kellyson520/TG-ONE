# 修复次级日志错误 (Fix Secondary Log Errors)

## Context
在完成了核心阻断性修复后，进一步检查日志发现如下遗留问题：
1.  **Corrupted Session File**: `db_maintenance_service` 在扫描备份目录时因损坏的 `.session` 文件抛出 ERROR。
2.  **Auth Flow Confusion**: 登录流程中出现 "用户名不存在" 紧接着 "Created admin" 的日志，逻辑显得突兀，需确认是否为正常行为或潜在 Bug。
3.  **Authentication Spam**: "Authentication failed" 警告日志过于频繁（正常访问未登录页面时），建议降级为 INFO。

## Strategy
1.  **Maintenance Service**: 修改扫描逻辑，自动跳过 `backup` 目录下的 `.session` 文件检查，或在遇到 `malformed` 错误时优雅降级。
2.  **Auth Router**: 优化登录逻辑，如果是首次登录触发的环境变量创建管理员，应理顺日志顺序或抑制预期的 "User not found" 警告。
3.  **Log Tuning**: 调整安全中间件的日志级别。

## Checklist

### Phase 1: Maintenance Service Fix
- [x] 分析 `services/db_maintenance_service.py`
- [x] 优化权限检查逻辑，忽略 `backup` 目录或捕获 SQLite 错误
- [x] 验证修复 (模拟损坏文件测试)

### Phase 2: Auth Flow Optimization
- [x] 分析 `web_admin/routers/auth_router.py`
- [ ] 优化 Admin 自动创建逻辑与日志
- [x] 调整 `web_admin/security/deps.py` 中的日志级别

### Phase 3: Verification
- [ ] 重启验证日志输出
- [ ] 确认 ERROR/WARNING 数量显著减少
