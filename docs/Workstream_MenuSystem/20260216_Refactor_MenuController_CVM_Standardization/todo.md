# Task: MenuController 及相关领域控制器架构标准化重构

## 1. 背景 (Background)
`MenuController` 曾负责大部分菜单的顶级编排，但部分方法（如 `show_help_guide`, `show_history_messages`, `show_rule_management`）存在硬编码 UI 逻辑或直接调用 Handler 模块的问题，不符合 CVM (Controller-View-Module) 架构规范。

## 2. 目标 (Objectives)
- [x] 重构 `MenuController.show_help_guide` 以使用 `MenuRenderer`。
- [x] 将历史任务/消息中心逻辑从 `MenuController` 迁移/收敛至 `MediaController`。
- [x] 将规则管理列表页委派给 `RuleController`。
- [x] 修复 `MenuController` 中的编码混乱问题（📖 等 Emoji 乱码）。
- [x] 确保所有 UI 渲染通过 `self.container.ui` 下的专用 Renderer 完成。

## 3. 方案设计 (Spec)
### 3.1 控制层 (Controllers)
- `MenuController`: 仅保留顶级 Hub 编排，其他具体业务功能通过 `self.container.{domain}_controller` 委托。
- `MediaController`: 承接所有历史任务 (Task List, Selector, Progress) 的业务逻辑。
- `RuleController`: 承接规则管理列表的展示。

### 3.2 表现层 (UI)
- `MenuRenderer` (Facade): 统一输出 `help_guide`, `faq`, `detailed_docs`。
- `TaskRenderer`: 统一输出历史任务相关的配置页与列表页。

## 4. 进度记录 (Todo)
- [x] 重构 `show_help_guide` & `show_faq` & `show_detailed_docs`
- [x] 迁移 `show_history_messages` (Hub) 至 `MediaController`
- [x] 迁移 `show_history_task_selector` & `show_current_history_task` 至 `MediaController`
- [x] 迁移 `show_rule_management` 至 `RuleController`
- [x] 修复 `NewMenuSystem` 中的路由代理，确保全链路遵循 CVM 模式
- [x] 验证 `show_task_actions` 的数据驱动渲染（引入真实时间范围显示）
