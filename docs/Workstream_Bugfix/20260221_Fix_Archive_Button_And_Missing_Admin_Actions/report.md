# 修复归档按钮缺失与后台管理动作失效

## 背景 (Context)
在最近的菜单系统重构中，部分后台管理动作（Admin Actions）未能在新的策略模式（Strategy Pattern）中完全适配，导致以下问题：
1. **归档按钮消失**：主系统设置面板（System Hub）中缺失了“归档中心”入口。
2. **后台动作失效**：清理维护菜单中的“释放磁盘空间”、“全面优化”等按钮点击后无响应或提示 `Unmatched action`。
3. **MenuController 代理缺失**：部分后台动作所需的 proxy 方法在 `MenuController` 中缺失。

## 修复方案 (Solution)

### 1. UI 增强 (UI Enhancement)
- **`AdminRenderer`**: 在 `render_system_hub` 方法中重新加入了“归档中心”按钮，确保用户可以直接从系统设置进入冷热数据归档管理。
- **`SystemMenu`**: 在旧版系统设置菜单中同步加入了“数据库归档”入口，保持操作一致性。

### 2. 策略适配 (Strategy Fix)
- **`AdminMenuStrategy`**: 
    - 补全了 `admin_vacuum_db` (释放空间)、`admin_analyze_db` (分析建议)、`admin_full_optimize` (全量优化) 的处理逻辑。
    - 修正了 `admin_cleanup` 的方法调用名为 `execute_admin_cleanup_logs`。
    - 补全了 `admin_stats` 和 `admin_config` 的路由。

### 3. 控制器对齐 (Controller Alignment)
- **`MenuController`**: 补全了以下代理方法：
    - `execute_admin_cleanup_logs`
    - `execute_cleanup_temp`
    - `show_admin_stats`
    - `show_config`

## 验证结果 (Verification)
- [x] 系统设置面板已显示“归档中心”按钮。
- [x] 点击“释放磁盘空间”能够触发数据库 `REINDEX/VACUUM` 逻辑。
- [x] “清理管理”菜单中的各项功能恢复正常。
- [x] 归档中心各子功能（手动归档、压缩归档等）路由正常。
