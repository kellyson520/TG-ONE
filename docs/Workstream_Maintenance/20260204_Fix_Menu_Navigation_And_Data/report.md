# 任务交付报告: 修复菜单导航与虚假数据展示

## 任务摘要 (Summary)
成功修复了 Bot 菜单系统中的导航循环问题、系统中心数据的真实接入以及数据库归档任务的并发崩溃问题。

## 修复说明 (Fixes)

### 1. 菜单导航 (Menu Navigation)
- **发现问题**: `RulesMenu.show_rule_management` 中的"返回上一级"按钮指向了自身 (`new_menu:forward_management`)，导致点击无反应（原地跳转）。
- **修复方案**: 修改 `RulesMenu` 中的相关返回按钮，使其正确指向转发中心 (`new_menu:forward_hub`)。

### 2. 系统中心数据 (Real Data Integration)
- **发现问题**: 系统设置中心展示的"转发规则"、"智能去重"、"数据记录"均为"未知"，且缺失 CPU/内存信息。原因是 `AnalyticsService` 返回的字段与 `MainMenuRenderer` 期望的不一致。
- **修复方案**:
    - 重构 `AnalyticsService.get_system_status`。
    - 接入 `psutil` 获取真实的 CPU、内存使用率和运行时间。
    - 接入数据库统计真实的规则总数/启用数。
    - 检查 `smart_deduplicator` 配置获取真实的去重开关状态。
    - 验证 `RuleLog` 表获取真实的数据记录状态。

### 3. 归档崩溃 (Archive Crash Fix)
- **发现问题**: 在 `archive_force` (强制归档) 的分批处理循环中，代码在 `session.commit()` 之后尝试访问已删除对象的 `.id` 属性，触发 SQLAlchemy 的 `ObjectDeletedError`。
- **修复方案**: 在执行删除和提交操作前，预先提取并保存 `last_id` 的数值，确保循环能安全继续。

## 验证结果 (Verification)
- **代码审计**: 确认所有 `callback_data` 引用路径闭环。
- **数据一致性**: 验证 `system_status` 返回字典与 UI 渲染器模板完全匹配。
- **稳定性**: `archive_force` 逻辑现在是内存安全的，不会再因对象失效而崩溃。

## 结论
系统关键 UI 路径已恢复，数据展示已全面真实化，数据库维护作业稳定性显著提升。
