# Task Report: 历史任务列表架构重构 (History Task List Architecture Refactoring)

## 1. 任务概述 (Task Overview)
- **核心目标**: 消除 `MenuController` 中硬编码的渲染与数据获取逻辑，将其迁移至 `MediaController`，实现严格的架构分层。
- **解决问题**: 修复了 `show_history_task_list` 直接在调度层实例化渲染器并操作 Repo 的不规范行为。

## 2. 变更详情 (Changes)

### 2.1 表现层 (UI)
- 保持 `TaskRenderer.render_history_task_list` 逻辑不变，但确保其通过标准的 `self.container.ui.task` 路径被调用，从而支持全局的单例注入和配置一致性。

### 2.2 控制层 (CVM Alignment)
- **`MediaController`**: 承接了原本位于 `MenuController` 的业务逻辑。现在负责：
    1. 通过 `task_repo` 查询历史迁移任务分页数据。
    2. 调用渲染器生成视图。
    3. 通过 `new_menu_system` 进行页面分发。
- **`MenuController`**: 重构后成为纯净的路由入口，仅负责将 `show_history_task_list` 请求转发至 `MediaController`。

## 3. 验证结果 (Verification)
- [x] **架构合规**: 调度层不再包含业务细节。
- [x] **功能完整性**: 历史任务列表（翻页、任务状态图标显示）保持正常。
- [x] **解耦验证**: 移除手动实例化 `TaskRenderer`，改用 IoC (Container) 管理的 UI 实例。

## 4. 结论 (Conclusion)
历史任务模块已完成架构对齐，消除了代码冗余及潜在的维护风险。
