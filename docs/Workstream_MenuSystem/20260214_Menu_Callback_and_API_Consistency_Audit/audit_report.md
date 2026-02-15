# 菜单与系统功能深度审计报告 (Deep Audit Report)

## 0. 审计概述
本次审计针对 bot 菜单及 Web 管理后台的展示真实性、功能完备性以及链路通畅情况进行了全方位扫描。

## 1. 虚假数据问题 (Fake/Mock Data)

### 1.1 Bot 菜单 (Telegram)
- **数据库管理**: `AdminController` 中的 `show_backup_management` 备份时间（2026-02-09）和备份计数（5）为硬编码。
- **垃圾清理**: `show_cache_cleanup` 中的文件大小（1.2MB, 450KB, 12MB）为假数据。
- **优化配置**: `show_db_optimization_config` 显示的配置（auto_vacuum=True等）为静态模拟值。
- **分析汇总**: `AnalyticsService` 在数据库查询失败或无数据时，会回退到硬编码的 70% 文本 / 30% 媒体比例。
- **性能指标**: 平均响应时间在无数据时默认显示 `0.1s`。

### 1.2 Web 管理后台 (Frontend)
- **仪表盘统计**: `Dashboard.tsx` 中的“七日转发趋势”图表完全基于硬编码的 `trafficData`。
- **消息类型**: 饼图数据 `messageTypeData` 为固定比例，未接入后端 `/api/stats/distribution`。
- **实时动态**: 右下角的“实时动态”列表 `activityLogs` 为预设的 5 条模拟消息。
- **系统资源**: 内存与 CPU 虽然有接入，但 `avg_delay`（平均延迟）在 API 层硬编码为 `0s`。

## 2. 功能缺失/占位符 (Functional Gaps)

### 2.1 Bot 菜单 (Telegram)
- **数据分析中心**: 以下功能点击后仅弹出“开发中”提示，无实际逻辑：
    - `anomaly_detection` (异常扫描)
    - `performance_analysis` (性能剖析)
    - `detailed_analytics` (详细报告)
    - `export_csv` (导出 CSV)
- **历史任务**: `show_history_task_list` 提示“🚧 列表功能正在集成中”。

### 2.2 Web 管理后台 (Frontend)
- **任务管理**: 部分操作按钮（如“导出日志”）仅触发通知提醒，未触发实际下载逻辑。
- **节点可视化**: `Visualization.tsx` 中部分复杂树结构的交互存在 TypeScript 类型断裂，导致渲染可能异常。

## 3. 链路通畅性 (Connection & Consistency)

### 3.1 接口冲突 (API Conflicts)
- **路由重叠**: 存在两个统计路由：`/api/stats` 与 `/api/system/stats`，职责划分模糊，导致前端不同页面调用的统计口径不一致。
- **指令冲突**: `NewMenuSystem` 与旧的 `MenuHandlerRegistry` 在部分指令（如 `RulesMenu`）上存在定义重叠，可能导致回调被多次处理或处理链异常。

### 3.2 丢失的链路 (Missing Links)
- **前缀丢失**: `media_settings` 和 `ai_settings` 在部分深度跳转中缺少 `new_menu:` 前缀，导致按钮点击无响应。
- **二级路由**: `rule_settings:{id}` (旧格式) 与 `rule:{id}:settings` (新格式) 在 `MenuController` 中共存，尚未完全收敛到新架构。

## 4. 修复建议 (Next Steps)
1. **真实数据化**: 优先将 `Dashboard.tsx` 的图表组件接入 `/api/stats/series`。
2. **功能补全**: 为 `AnalyticsMenuStrategy` 接入真实的 `AnalyticsService` 聚合逻辑。
3. **接口收敛**: 废弃 `/api/stats`，统一使用 `/api/system/stats`。
4. **前缀规范**: 强制所有回调 Key 经过 `UIRE-3.0` 验证器。

---
**审计人**: Antigravity AI
**日期**: 2026-02-14
