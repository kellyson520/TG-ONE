# 统一命令与菜单系统 UI (Unified Command & Menu System UI)

## 背景 (Context)
当前系统中，机器人的“反斜杠命令（Slave Commands）”与“交互式菜单（Interactive Menu）”在用户体验上是割裂的。命令通常返回简单的文本，而菜单系统使用精美的按钮和格式化输出。用户希望这两者共用一套 UI，无论通过何种方式触发，都能获得一致的、现代化的视觉反馈。

## 策略 (Strategy)
1.  **视图共享 (View Sharing)**：所有命令处理程序必须利用 `ui/renderers/` 中的渲染器来生成响应。
2.  **入口对齐 (Entrypoint Alignment)**：将命令映射到 `NewMenuSystem` 的对应模块。
3.  **上下文衔接 (Context Continuity)**：通过命令触发的 UI 应包含“返回”或“前往相关菜单”的按钮，实现无缝切换。
4.  **架构协同**：配合 `20260208_Refactor_Menu_System` 任务，确保所有逻辑都在 `Strategy` 类中。

## 分阶段检查清单 (Phase Checklist)

### Phase 1: 规划与设计 (Planning & Design)
- [ ] 制定命令到菜单视图的完整映射表 (`spec.md`)
- [ ] 统一消息模版风格 (Title/Separator/Content/Buttons)
- [ ] 获取用户对设计方案的审查确认

### Phase 2: 响应机制重构 (Response Refactoring)
- [ ] 创建 `services/ui_response_service.py` 统一处理命令响应
- [ ] 更新 `BotHandler.handle_command` 以支持跳转到菜单系统
- [ ] 移除 `rule_commands.py` 等文件中硬编码的文本回复，改为调用渲染器

### Phase 3: 模块化集成 (Modular Integration)
- [ ] **3.1 规则管理对齐**：`/list_rule` -> 列表菜单，`/settings` -> 详情菜单
- [ ] **3.2 系统管理对齐**：`/system_status`, `/update`, `/rollback` -> 系统中心
- [ ] **3.3 内容搜索对齐**：`/search` -> 搜索界面
- [ ] **3.4 QoS 对齐**：`/vip`, `/queue_status` -> 优先级看板

### Phase 4: 验证与优化 (Verification & Polish)
- [ ] 校验所有命令触发后的 UI 是否含有导航按钮
- [ ] 针对 Windows 终端/Telegram Desktop 进行适配性检查
- [ ] 最终功能验收与报告
