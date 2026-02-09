# TG ONE UI 渲染引擎升级方案 (Proposal)

## 1. 背景与现状分析 (Context)
当前的 UI 渲染逻辑在 `ui/renderers/` 目录下各司其职，但存在明显的代码重复和模式过时问题：

- **高度重复的模板代码**：每个 `render_xxx` 方法都在手动拼接 `━━━━━━━━━━━━━━` 分割线以及标题装饰。
- **逻辑与布局耦合**：Controller 传入的数据需要手动映射到字符串中，缺乏语义化的组件化能力。
- **图标使用混乱**：`UIStatus` 图标被手动硬编码在字符串中，修改图标需要批量更新几十处代码。
- **维护成本高**：如果需要统一修改全系统的“回退”按钮样式，必须修改每一个 Renderer。

## 2. 升级目标 (Objectives)
1. **DRY (Don't Repeat Yourself)**：消除所有硬编码的模板文本。
2. **抽象化布局**：引入 `MenuBuilder` 实现流式构建界面。
3. **视觉一致性**：自动处理标题、分割线、面包屑和按钮排列规范。
4. **易于扩展**：支持组件化（如：`StatusBadge`, `ProgressBar`）。

## 3. 技术方案 (Proposed Solution)

### 3.1 引入 `MenuBuilder` (链式调用引擎)
创建一个语义化的构建器，将菜单拆解为：`Header` (标题+面包屑), `Body` (内容块), `Action` (按钮区域)。

### 3.2 拟议核心 API
```python
class MenuBuilder:
    def set_title(self, text: str, icon: str) -> 'MenuBuilder'
    def add_breadcrumb(self, path: List[str]) -> 'MenuBuilder'
    def add_section(self, header: str, content: Union[str, List[str]]) -> 'MenuBuilder'
    def add_status_grid(self, items: Dict[str, Any]) -> 'MenuBuilder'
    def add_button(self, label: str, action: str, icon: str = None) -> 'MenuBuilder'
    def build(self) -> ViewResult
```

### 3.3 示例对比 (Refactoring Sample)

#### [BEFORE] 旧版 AdminRenderer
```python
def render_system_hub(self, data: Dict[str, Any]) -> ViewResult:
    text = (
        f"{UIStatus.SETTINGS} **系统设置中心**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛠️ **底层能力管理**\n"
        f"管理项目的数据库备份、垃圾清理及底层存储优化。\n\n"
        f"📈 **健康度指标**\n"
        f"• 数据库状态: {UIStatus.SUCCESS} 正常\n"
    )
    buttons = [[Button.inline(f"{UIStatus.BACK} 返回", "main_menu")]]
    return ViewResult(text=text, buttons=buttons)
```

#### [AFTER] 升级后的新模式
```python
def render_system_hub(self, data: Dict[str, Any]) -> ViewResult:
    return (MenuBuilder()
        .set_title("系统设置中心", icon=UIStatus.SETTINGS)
        .add_breadcrumb(["首页", "设置"])
        .add_section("底层能力管理", "管理项目的数据库备份、垃圾清理及底层存储优化。")
        .add_status_grid({
            "数据库状态": ("正常", UIStatus.SUCCESS),
            "核心引擎": ("运行中", UIStatus.SUCCESS)
        })
        .add_button("返回主菜单", action="main_menu", icon=UIStatus.BACK)
        .build())
```

## 4. 实施阶段 (Phases)
- **Phase 1**: 实现 `ui/builder.py` 核心引擎及 `ViewResult` 的扩展支持。
- **Phase 2**: 在 `BaseRenderer` 中注入 Builder。
- **Phase 3**: 迁移 `AdminRenderer` 作为试点。
- **Phase 4**: 全量迁移并移除冗余的字符串模板。

## 5. 优势点
- **极速开发**：开发者只需关注内容，无需关心各种表情符号的排列。
- **动态适配**：Builder 可以自动检测按钮文本长度，决定一行放 2 个还是 3 个按钮。
- **皮肤系统**：未来只需修改 Builder，即可实现全系统黑暗模式/精简模式切换。

---
**审核意见：** 请回复 `同意` 或 `修改意见` 以继续。
