# 技术方案: 多源管理布局优化 (Spec: Multi-Source Management Layout Optimization)

## 背景
用户希望“多源管理”成为一个快速开关页面。

## 变更列表

### 1. 视图层 (`handlers/button/modules/rules_menu.py`)
- **方法**: `show_multi_source_management`
- **逻辑**: 
    - 遍历规则时，检查 `rule.enable_rule`。
    - 按钮文案格式: `{状态图标} {动作} 规则{id}: {源}➔{目标}`
    - 示例: `🟢 开启 规则5: A➔B` (点它会关闭) 或 `🔴 关闭 规则5: A➔B` (点它会开启)
    - 回调 Data: `new_menu:toggle_rule:{id}:multi:{page}`

### 2. 策略分发层 (`handlers/button/strategies/rules.py`)
- **逻辑**:
    - 解析 `toggle_rule` 的 `extra_data`。
    - 如果 `len(extra_data) > 1` 且 `extra_data[1] == 'multi'`，则将 `from_page='multi'` 和 `page=extra_data[2]` 传递给控制器。

### 3. 控制器层 (`controllers/domain/rule_controller.py`)
- **方法**: `toggle_status(self, event, rule_id: int, from_page: str = 'detail', page: int = 0)`
- **逻辑**:
    - 执行切换。
    - 根据 `from_page` 决定下一步操作：
        - `detail` (默认): `show_detail(event, rule_id)`
        - `multi`: `show_multi_source_management(event, page)`

## 架构考虑
- 避免直接在 Strategy 调用 View，通过 Controller 转换。
- 维持 `NewMenuSystem` 的代理职责。
