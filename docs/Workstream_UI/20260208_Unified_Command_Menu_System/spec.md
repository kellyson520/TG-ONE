# 统一 UI 设计方案 (Unified UI Design Specification)

## 1. 核心视觉规范 (Visual Specification)

所有机器人响应消息应遵循以下“三段式”结构：

1.  **Header (页眉)**: 
    - 使用 Emoji + 粗体标题。
    - 示例: `🌌 **Telegram 智能中枢**` 或 `⚙️ **系统设置中心**`。
2.  **Body (正文)**:
    - 使用特殊分隔符（如 `━━━` 或 `➖➖➖`）。
    - 关键数据使用代码块（backticks）包裹以便复制。
    - 列表项使用统一的 bullet points (├─, └─)。
3.  **Footer/Menu (页脚/菜单)**:
    - 底部必须包含上下文相关的 Inline Buttons。
    - 统一样式：[🏠 返回主菜单] [🔄 刷新] [❓ 帮助]。

## 2. 命令与菜单映射表 (Command-Menu Mapping)

| 命令 | 目标菜单方法 (NewMenuSystem) | 附加逻辑 |
| :--- | :--- | :--- |
| `/menu`, `/settings` | `show_main_menu` | 直接唤起根节点 |
| `/list_rule`, `/lr` | `show_rule_list` | 显示分页列表，每行带详情按钮 |
| `/status`, `/system_status`| `show_system_status` | 集成 QoS/优先级队列信息 |
| `/update`, `/rollback` | `show_system_hub` | 执行后自动刷新系统状态界面 |
| `/search` | `show_forward_search` | 进入搜索配置/结果模式 |
| `/bind` | `show_rule_detail_settings` | 成功后跳转到该规则的详情页 |
| `/vip`, `/qs` | `show_qos_看板` (待创建) | 新增一个专门的优先级队列监控页 |

## 3. 技术实现架构 (Technical Architecture)

### 3.1 统一响应桥接 (The Bridge)

在 `handlers/bot_handler.py` 中引入 `Navigator` 模式：

```python
async def handle_command(event, client, parts):
    # ... 解析命令 ...
    if command in UI_MAPPED_COMMANDS:
        # 内部重定向到菜单系统
        await new_menu_system.dispatch_from_command(command, event)
    else:
        # 旧命令或无 UI 命令继续走旧路径
        await handler()
```

### 3.2 渲染器解耦 (Renderer Decoupling)

`ui/renderers/` 中的类应不仅支持回调查询（CallbackQuery），也应能够处理原始消息事件（Message Event）。

### 3.3 无缝交互体验 (UX Flow)

- **Input Detection**: 处于“等待输入”状态（如添加关键字）时，顶部的菜单消息应更新为“监听中...”状态。
- **Auto-Cleanup**: 触发新菜单时，自动删除或覆盖之前的指令消息，保持聊天界面整洁。

## 4. 关键 UI 改进提案 (Key UI Enhancements)

- **QoS 看板**: 实现在菜单中实时查看 VIP 规则命中情况、队列堆积数的仪表盘。
- **动态更新**: 对于 `/update` 等耗时操作，UI 应展示动态进度条（利用 `Button.edit`）。

---
**确认项**:
1. 用户是否同意移除所有纯文本命令回复？
2. 是否需要在菜单中增加一个“快速指令”区域显示常用 `/` 命令的快捷键？
