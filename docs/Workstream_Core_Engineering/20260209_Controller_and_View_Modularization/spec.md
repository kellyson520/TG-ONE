# CVM (Controller-View-Modularization) 技术方案规范

## 1. 背景 (Background)
当前 `MenuController` 过于臃肿 (约 2000+ 行)，且 UI 渲染逻辑与业务控制逻辑高度耦合。为了提高可维护性和测试性，执行此重构，将职责拆分为：
- **Controllers**: 负责业务逻辑、权限校验、状态变更。
- **Views/Renderers**: 负责文本拼接、按钮构建、数据可视化。
- **Handlers**: 负责接收 Telegram 事件并桥接到 Controller。

## 2. 核心协议 (Core Protocols)

### 2.1 ViewResult 数据结构 (P0.1)
统一 View 层返回给 Controller/Handler 的数据格式。

```python
from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

@dataclass
class ViewResult:
    """统一视图渲染产物"""
    text: str
    buttons: List[List[Any]] = field(default_factory=list)  # Any 通常为 InlineKeyboardButton
    parse_mode: str = "html"
    file: Optional[Union[str, bytes]] = None
    file_type: Optional[str] = None  # "photo", "document", "video"
    force_new_message: bool = False  # 是否强制发送新消息而非编辑
    notification: Optional[str] = None  # 回调按钮的顶部弹窗提示 (answerCallbackQuery)
    show_alert: bool = False  # 如果有 notification，是否以 Alert 形式显示
    context_update: Optional[dict] = field(default_factory=dict) # 可选：需要更新到 UserContext 的状态
```

### 2.2 回退 (Back) 导航协议 (P0.2)
在 `BaseView` 中定义通用的回退按钮构建方法。

```python
class BaseView:
    @staticmethod
    def build_back_button(target_action: str) -> list:
        """统一回退按钮，target_action 为回调指令"""
        return [InlineKeyboardButton("⬅️ 返回", callback_data=target_action)]
```

### 2.3 消息操作决策逻辑 (P0.4)
定义如何决定是 `edit` 还是 `respond`。
- **默认优先 `edit`**: 保持用户会话整洁。
- **强制 `respond`**:
    - 用户手动输入的指令 (MessageEvent)。
    - 需要保留历史轨迹的操作。
    - 切换模块（如从“管理”跳到“规则”）且视觉风格差异巨大时。

### 2.4 异常 UI 渲染标准 (P0.5)
替代简单的 `print` 或弹窗。

```python
class ErrorView(BaseView):
    @staticmethod
    def render_error(error_msg: str, back_target: str = "main_menu") -> ViewResult:
        text = f"❌ <b>操作失败</b>\n\n原因: {error_msg}\n\n点按下方按钮返回。"
        buttons = [BaseView.build_back_button(back_target)]
        return ViewResult(text=text, buttons=buttons)
```

## 3. 架构分层 (Layering)

### 3.1 基础控制器 (BaseController)
```python
class BaseController:
    def __init__(self, container):
        self.container = container
        self.db = container.db
        self.ui = container.ui  # 访问各种渲染器

    async def get_rule_or_abort(self, rule_id: int):
        rule = await self.container.rule_repo.get_by_id(rule_id)
        if not rule:
            raise ControllerAbort("该规则不存在或已被删除")
        return rule
```

### 3.2 目录结构 (P1.1)
- `controllers/`
    - `base.py`
    - `domain/` (拆分后的各领域控制器)
        - `rule_controller.py`
        - `admin_controller.py`
        - `media_controller.py`
    - `legacy/` (暂存未拆分完的旧逻辑)
- `ui/`
    - `constants.py` (图标、颜色)
    - `renderers/` (原有渲染器)
    - `components/` (通用组件，如分页器)

## 4. 实施细节 (Implementation)

### 4.1 分页器组件化 (P1.2)
实现一个 `Paginator` 类，接收 `List[Any]`，返回当前页的项目及导航按钮。

### 4.2 依赖注入 (P1.5)
在 `core/container.py` 中：
```python
self.rule_controller = Singleton(RuleController, container=self)
self.admin_controller = Singleton(AdminController, container=self)
```
