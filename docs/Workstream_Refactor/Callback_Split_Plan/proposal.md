# Refactor Proposal: Modularize Callback Handlers
## 问题分析
目前 `handlers/button/callback/new_menu_callback.py` 文件体积过大 (**约 2500+ 行**)，集成了过多的业务逻辑。
违反了 **单一职责原则 (SRP)**，导致：
1.  **可维护性差**：修改任何一个小功能都需要打开巨大的文件。
2.  **合并冲突**：多人开发时极易产生冲突。
3.  **阅读困难**：逻辑跳转复杂，不易梳理业务流程。
4.  **调试困难**：错误定位和上下文追踪变得复杂。

## 目标
将 `new_menu_callback.py` 拆解为多个 **功能单一、职责明确** 的子模块，通过 **注册机制 (Registry)** 或 **分发器 (Dispatcher)** 进行统一管理。
目标是将主入口文件缩减至 **200 行以内**。

## 架构设计方案 (Router Pattern)

### 1. 目录结构重构
我们将创建 `handlers/button/callback/modules/` 目录，并按功能域拆分：

```text
handlers/button/callback/
├── __init__.py                # 暴露统一入口
├── dispatcher.py     # [Generic] 核心分发器 (Router)
├── new_menu_callback.py       # [Legacy] 逐步迁移的存量文件 (最终作为一个 Module 存在或消亡)
└── modules/                   # [New] 功能模块目录
    ├── __init__.py
    ├── root.py                # 主菜单、通用导航 (Main Menu, Hubs)
    ├── rules.py               # 规则管理 (List, Detail, Toggle, Delete)
    ├── rule_settings.py       # 规则配置 (Basic, Display, Advanced, Dedup)
        ├── keywords.py            # 关键词管理 (独立，因为逻辑较重)
        ├── replacement.py         # 替换规则管理
    ├── system.py              # 系统设置 (Backup, Cleanup, Logs)
    ├── session.py             # 会话管理 (List, Delete, Dedup)
    ├── analytics.py           # 数据统计 (Charts, Stats)
    ├── multi_source.py        # 多源管理 (Newly Added)
    └── common/                # 通用工具
        └── helpers.py         # 提取公共参数解析逻辑
```

### 2. 核心分发机制 (Dispatcher)
采用 **装饰器注册模式**，类似 Flask/FastAPI 的路由。

**`dispatcher.py` 示例:**
```python
# handlers/button/callback/dispatcher.py
import logging
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)

class CallbackDispatcher:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._prefix_handlers: Dict[str, Callable] = {} # 处理如 "toggle_*" 的前缀匹配

    def register(self, action_key: str):
        """装饰器：注册精确匹配的 Action"""
        def decorator(func):
            self._handlers[action_key] = func
            return func
        return decorator
    
    def register_prefix(self, prefix: str):
        """装饰器：注册前缀匹配的 Action"""
        def decorator(func):
            self._prefix_handlers[prefix] = func
            return func
        return decorator

    async def dispatch(self, event, action: str, extra_data: list, session, message):
        """分发逻辑"""
        # 1. 精确匹配
        if action in self._handlers:
            return await self._handlers[action](event, extra_data, session)
        
        # 2. 前缀匹配
        for prefix, handler in self._prefix_handlers.items():
            if action.startswith(prefix):
                 return await handler(event, action, extra_data, session)

        # 3. Fallback (可选：抛出异常或记录日志)
        logger.warning(f"未找到 Action 处理器: {action}")
```

### 3. 模块化实现示例

**`modules/rules.py` 示例:**
```python
# handlers/button/callback/modules/rules.py
from ..dispatcher import dispatcher
from controllers.menu_controller import menu_controller

@dispatcher.register("list_rules")
async def handle_list_rules(event, extra_data, session):
    page = int(extra_data[0]) if extra_data else 0
    await menu_controller.show_rule_list(event, page=page)

@dispatcher.register("rule_detail")
async def handle_rule_detail(event, extra_data, session):
    rule_id = int(extra_data[0]) if extra_data else 0
    await menu_controller.show_rule_detail(event, rule_id)
```

**`modules/root.py` 示例:**
```python
# handlers/button/callback/modules/root.py
from ..dispatcher import dispatcher
from controllers.menu_controller import menu_controller

@dispatcher.register("main_menu")
async def handle_main_menu(event, extra_data, session):
    await menu_controller.show_main_menu(event)
```

## 迁移路线图 (Migration Roadmap)

### Phase 1: 基础设施搭建 (Day 1)
1.  创建 `dispatcher.py` 和 `modules/` 目录结构。
2.  在 `new_menu_callback.py` 中引入 Dispatcher，并保留旧的 `if-elif` 逻辑作为 Fallback。
    -   *Logic*: `if dispatcher.dispatch(...): return; else: old_logic()`
3.  提取公共参数解析代码到 `common/helpers.py`.

### Phase 2: 模块拆分与迁移 (Day 1-2)
按功能块逐步迁移，每次迁移一个块并验证：
1.  **Group A (高频/简单)**: `root.py` (Main Menu, hubs), `system.py` (Backup, Cleanup).
2.  **Group B (核心业务)**: `rules.py` (Curd), `rule_settings.py` (Settings).
3.  **Group C (复杂逻辑)**: `keywords.py`, `replacement.py`, `session.py`, `analytics.py`.
4.  **Group D (新增/独立)**: `multi_source.py`.

### Phase 3: 清理与收尾 (Day 2)
1.  删除 `new_menu_callback.py` 中已被迁移的遗留代码。
2.  最终 `new_menu_callback.py` 仅作为入口，负责初始化 Dispatcher 并调用 `dispatch`。
3.  执行全量回归测试 (使用集成测试套件)。

## 预期收益
1.  **文件瘦身**: 单个文件不超过 300 行。
2.  **结构清晰**: 目录结构对齐业务领域。
3.  **开发效率**: 新增按钮只需在一个小文件中添加 `@register`，无需在千行代码中搜索 `elif`。

## 审核确认
请审核以上重构计划。确认后我将开始创建文件结构并执行 Phase 1。
