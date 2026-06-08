# Fix NewMenuSystem AttributeError Report

## Summary
修复了新菜单系统中由方法缺失导致的 `AttributeError`。该错误发生在智能去重设置页面跳转到时间窗口设置、高级设置等子页面时。

## Changes
1.  **SmartDedupMenu (`handlers/button/modules/smart_dedup_menu.py`)**:
    *   实现了 `show_dedup_time_window`: 提供时间窗口的选择与切换开关。
    *   实现了 `show_dedup_advanced`: 提供持久化缓存、SimHash 等高级配置入口及手动清理功能。
    *   实现了 `show_dedup_hash_examples`: 展示去重系统提取的消息特征示例。
    *   增强了 `show_dedup_statistics`: 添加了今日活跃会话统计。

2.  **NewMenuSystem (`handlers/button/new_menu_system.py`)**:
    *   添加了对上述新增方法的代理（Delegation），确保门面类能够响应回调请求。
    *   补全了 `show_dedup_statistics` 的代理。

3.  **AnalyticsMenu (`handlers/button/modules/analytics_menu.py`)**:
    *   实现了 `show_failure_analysis`: 提供今日成功率、错误计数及排障建议。

4.  **Callback Handler (`handlers/button/callback/new_menu_callback.py`)**:
    *   移除了 `failure_analysis` 的临时降级逻辑。

## Verification
*   代码逻辑已通过静态检查。
*   所有调用路径均已在 `NewMenuSystem` 中注册。
*   跳转逻辑与 `new_menu_callback.py` 中的 action 对齐。

## Manual
管理员在使用“智能去重中心”时，现在可以正常点击“时间窗口设置”、“高级设置”及“去重统计”。
如果需要查看失败原因，可以点击“数据分析中心” -> “失败分析”。
