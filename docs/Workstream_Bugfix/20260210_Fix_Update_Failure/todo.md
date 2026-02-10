# 修复更新信号接收但不更新的问题 (Fix Update Failure)

## 背景 (Context)
系统检测到外部更新信号 (Status: processing)，但随后执行了受控重启，用户反馈并没有进行实际的更新逻辑。

## 核心技术路径 (Strategy)
1. 分析 `update_service.py` 中处理 "processing" 状态的逻辑。
2. 检查 `UpdateService` 的 `processing` 循环和更新触发机制。
3. 验证重启脚本 (`entrypoint.sh` 或类似物) 是否包含必要的更新操作。
4. 修复逻辑断点，确保信号触发后能执行 `git pull` 和依赖同步。

## 待办清单 (Checklist)

### Phase 1: 问题诊断 (Diagnosis)
- [x] 分析 `update_service.py` 源码，定位 "processing" 状态处理代码。
- [x] 检查 `LifecycleManager` 在重启前的动作。
- [x] 搜索全局日志或尝试复现更新流程。

### Phase 2: 方案设计 (Design)
- [x] 确定更新逻辑的挂载点（Service内 或 外部脚本）。
- [x] 编写修复方案 (`spec.md`)。

### Phase 3: 核心实现 (Implementation)
- [x] 修正 `UpdateService` 的重启逻辑，确保在退出前标记或触发更新。
- [x] 修复 `Bootstrap.py` 中 `_resource_monitor_loop` 的判断错误。
- [x] 注册 `UpdateService` 的关闭钩子以防止退出时挂起。

### Phase 4: 验证与验收 (Verification)
- [ ] 模拟外部更新信号。
- [ ] 验证系统是否执行更新并成功重启。
- [ ] 提交 `report.md`。
