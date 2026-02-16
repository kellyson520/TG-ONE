# Task: 历史任务列表架构重构 (History Task List Architecture Refactoring)

## 1. 背景 (Background)
`MenuController.show_history_task_list` 方法中存在硬编码的业务逻辑（手动实例化 `TaskRenderer` 和调用 `task_repo`），违背了项目的控制器-领域控制器-渲染器 (CVM) 架构规范。

## 2. 目标 (Objectives)
- [x] 将历史任务列表的业务逻辑迁移至 `MediaController`。
- [x] 在 `MenuController` 中移除硬编码逻辑，改为委托调用。
- [x] 确保使用标准的 `self.container.ui.task` (TaskRenderer) 进行渲染。

## 3. 方案设计 (Spec)
### 3.1 表现层
- 继续使用 `TaskRenderer.render_history_task_list`。

### 3.2 控制层
- `MediaController`: 新增 `show_history_task_list` 方法，负责从 `task_repo` 获取数据并渲染。
- `MenuController`: 更新 `show_history_task_list` 仅作为路由转发。

## 4. 进度记录 (Todo)
- [x] 在 MediaController 中实现标准化的 show_history_task_list
- [x] 重构 MenuController 中的对应方法，移除硬编码实现
- [x] 验证跳转与渲染效果
