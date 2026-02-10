# 升级服务支持非 Git 环境 (Upgrade Update Service for Non-Git)

## 背景 (Context)
当前的自动更新服务（包括 `entrypoint.sh` 和 `UpdateService`）过度依赖 `git` 命令和本地 git 仓库。在某些精简环境（如某些 Docker 镜像或手动部署环境）中，`git` 可能未安装或未初始化，导致更新失败。

## 待办清单 (Checklist)

### Phase 1: 现状调研与方案设计
- [x] 分析 `scripts/ops/entrypoint.sh` 中的更新逻辑
- [x] 分析 `services/update_service.py` 中的版本检测与更新触发逻辑
- [x] 设计非 Git 环境下的备选更新方案（如压缩包下载或跳过源码同步）

### Phase 2: 核心代码重构 (entrypoint.sh)
- [x] 在 `entrypoint.sh` 中增加 `git` 检测
- [x] 实现非 Git 环境下的占位/备选逻辑（检测不到 git 则记录警告并继续重启逻辑）
- [x] 优化 Git 拉取失败后的容错处理

### Phase 3: Python 服务端适配 (UpdateService)
- [x] 修改 `UpdateService` 的版本获取逻辑，支持从 `VERSION` 文件或环境变量读取
- [x] 增加环境检测功能，标识当前是否处于 Git 环境
- [x] 禁封非 Git 环境下仅 Git 支持的操作（如 `git log` 查看变更，回退至状态文件信息）

### Phase 4: 验证与交付
- [x] 模拟非 Git 环境进行集成测试（单元测试已通过 mock 验证）
- [x] 验证更新失败后的回滚/恢复逻辑
- [ ] 提交任务报告并归档

### Phase 5: 优化非 Git 环境版本校验与显示
- [x] 实现版本指纹持久化至 `update_state.json`，清理冗余的 `VERSION` 文件
- [x] 修正 `_cross_verify_sha` 支持特定 SHA 校验（不限于分支 HEAD）
- [x] 优化 `get_current_version` 逻辑，支持 `update_state.json` 的深度查找
- [x] 修正 `_perform_http_update` 在同步后正确记录目标 SHA
- [x] 增强 `_check_via_http` 处理 short/long SHA 对比的兼容性
