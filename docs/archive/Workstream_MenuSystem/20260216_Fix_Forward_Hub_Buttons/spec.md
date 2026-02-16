# 技术方案: 转发中心按钮修复 (Spec: Forward Hub Buttons Fix)

## 背景
`render_forward_hub` 提供的 7 个功能按钮中，有 3 个在 `RuleMenuStrategy` 中被硬编码为“开发中”。本方案旨在将这些回调指向已有的 `AnalyticsMenu` 和 `FilterMenu` 实现。

## 映射逻辑 (Mapping Logic)

| 按钮名称 | 回调动作 (Action) | 目标处理函数 (Target Handler) | 归属模块 |
| :--- | :--- | :--- | :--- |
| 详细统计 | `forward_stats_detailed` | `analytics_menu.show_detailed_analytics` | `AnalyticsMenu` |
| 全局筛选 | `global_forward_settings` | `filter_menu.show_filter_settings` | `FilterMenu` |
| 性能监控 | `forward_performance` | `analytics_menu.show_performance_analysis` | `AnalyticsMenu` |

## 实施步骤
1. 修改 `e:\重构\TG ONE\handlers\button\strategies\rules.py`：
   - 在 `handle` 方法中，移除原有的 `await event.answer("...开发中", alert=True)`。
   - 替换为调用 `new_menu_system` 中对应的代理方法。

2. 验证 `new_menu_system.py` 中的方法存在性：
   - `show_detailed_analytics` -> 已存在
   - `show_filter_settings` -> 已存在
   - `show_performance_analysis` -> 已存在

## 架构影响
- 保持 DDD 分层。
- 使用 `NewMenuSystem` 作为中转代理，避免各 Strategy 直接引用具体的 Menu 模块（解耦）。
