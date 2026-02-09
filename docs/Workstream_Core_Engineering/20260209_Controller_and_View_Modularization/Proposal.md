# 控制器与视图模块化重构方案 (Controller & View Modularization Proposal)

## 0. 现状评估 (Current Audit)
*   **文件路径**: `controllers/menu_controller.py`
*   **代码规模**: 1400+ 行
*   **主要痛点**: 
    1.  **职责耦合**: 同时处理数据库服务调用、多语言文本拼接、复杂的 Telegram 按钮数组构建。
    2.  **维护成本**: 修改一个 UI 图标需要深入到 1000 行后的控制器内部，极易引发回归错误。
    3.  **测试困难**: 逻辑与 Telegram UI 组件（Button）高度绑定，无法进行无界面的逻辑单元测试。

---

## 1. 目标架构 (Target Architecture)

重构将遵循 **Clean Architecture** 的变体，引入专门的渲染层：

### 1.1 目录结构变更
```bash
controllers/
├── __init__.py
├── menu_facade.py      # 继承/代理所有子控制器，保持外部接口不变（兼容模式）
├── rule_controller.py   # 处理规则 CRUD 逻辑流
├── admin_controller.py  # 系统维护、日志、备份
├── media_controller.py  # 媒体过滤、AI 设置、去重配置
└── task_controller.py   # 异步任务、分析中心

ui/
└── renderers/
    ├── base.py          # 基础渲染工具（格式化时间、图标转换）
    ├── rule_view.py     # 规则详情、列表、详情页按钮构建
    ├── admin_view.py    # 管理面板、数据库状态 UI
    └── system_view.py   # 主仪表盘、分析中心 UI
```

### 1.2 逻辑分离示例 (Before vs After)

**重构前 (Controller 承担所有职责):**
```python
async def show_rule_detail(self, event, rule_id):
    rule = await self.service.get_rule(rule_id)
    text = f"**规则详情**\nID: {rule.id}\n状态: {'✅' if rule.enable else '❌'}"
    buttons = [
        [Button.inline("开启" if not rule.enable else "关闭", f"new_menu:toggle_rule:{rule.id}")]
    ]
    await event.edit(text, buttons=buttons)
```

**重构后 (Controller 只负责调度，View 负责呈现):**
```python
async def show_rule_detail(self, event, rule_id):
    # 1. 业务调度
    rule = await self.rule_service.get_rule_detail(rule_id)
    # 2. UI 委派
    text, buttons = RuleView.render_detail(rule)
    # 3. 执行输出
    await event.edit(text, buttons=buttons)
```

---

## 2. 实施路线图 (Implementation Roadmap)

### 阶段 1：基础设施与 View 层建立 (Setup)
- [ ] 创建 `ui/renderers/` 目录并定义 `BaseView`。
- [ ] 提取 `MenuController` 中的公共 UI 组件（如：分页按钮构建器）。

### 阶段 2：领域控制器拆分 (Modularization)
- [ ] **2.1 规则领域**: 迁移 `list_rules`, `rule_detail`, `sync_config` 等至 `RuleController`。
- [ ] **2.2 管理领域**: 迁移备份、重启、数据库健康检查至 `AdminController`。
- [ ] **2.3 媒体与 AI**: 迁移大小限制、后缀过滤、AI 提示词配置至 `MediaController`。

### 阶段 3：Facade 模式集成 (Integration)
- [ ] 将 `menu_controller.py` 重构为 `MenuFacade` 类，通过组合（Composition）方式调用以上子控制器。
- [ ] 确保 `strategies/` 层的调用无需修改代码即可运行。

### 阶段 4：净化与验证 (Validation)
- [ ] **God File 消除**: 验证单文件行数降至 500 行以下。
- [ ] **单元测试**: 为拆分后的控制器添加逻辑单元测试。

---

## 3. 验收标准 (Acceptance Criteria)
1.  **物理规模**: 没有任何控制器文件超过 600 行。
2.  **职责纯度**: 控制器内严禁出现字符串模板（f-string 定义 UI 文本）。
3.  **兼容性**: 所有的 Telegram 菜单点击动作功能完全正常。
4.  **性能**: CPU 加载时长不增加，内存占用保持在 2GB 限制内。
