# 任务清单：回调处理器重构 (Callback Handler Refactor)

## 第一阶段：基础设施搭建 (Phase 1: Infrastructure)
- [ ] **创建目录结构**
    - 创建 `handlers/button/callback/modules/`
    - 创建 `handlers/button/callback/modules/common/`
- [ ] **实现分发核心 (Dispatcher)**
    - 创建 `handlers/button/callback/dispatcher.py` 包含 `CallbackDispatcher` 类
    - 实现 `@register(action)` 装饰器逻辑
    - 实现 `@register_prefix(prefix)` 装饰器逻辑
    - 实现基于 `action` 字符串的路由分发方法 `dispatch`
- [ ] **初始化模块入口**
    - 创建 `handlers/button/callback/modules/__init__.py` 暴露各子模块
    - 创建 `handlers/button/callback/modules/common/helpers.py` 封装参数解析与状态管理
- [ ] **集成旧代码**
    - 修改 `new_menu_callback.py` 引入 `dispatcher`
    - 在主入口函数优先调用 `dispatcher.dispatch`
    - 保留原有 `if-elif` 作为后备逻辑 (Fallback)

## 第二阶段：模块迁移与拆分 (Phase 2: Module Migration)

### 组 A: 系统与核心导航 (Key: `root.py`, `system.py`)
- [ ] **迁移主菜单与中心 (root.py)**
    - 迁移 `main_menu`, `main_menu_refresh`
    - 迁移 `forward_hub`, `dedup_hub`, `analytics_hub`, `system_hub`
    - 迁移 `help_guide`, `faq`, `detailed_docs`
- [ ] **迁移系统操作 (system.py)**
    - 迁移 `db_backup`, `do_backup`, `view_backups`, `restore_backup`
    - 迁移 `cache_cleanup`, `do_cleanup`
    - 迁移 `system_settings`, `system_overview`
    - 迁移 `run_db_reindex`, `db_clear_alerts`, `dedup_clear_cache`

### 组 B: 业务逻辑核心 (Key: `rules.py`, `rule_settings.py`, `keywords.py`)
- [ ] **迁移规则 CRUD (rules.py)**
    - 迁移 `list_rules`, `rule_detail`
    - 迁移 `toggle_rule`, `delete_rule_confirm`, `delete_rule_do`
- [ ] **迁移规则配置 (rule_settings.py)**
    - 迁移 `rule_basic_settings`, `rule_display_settings`, `rule_advanced_settings`
    - 迁移 `toggle_rule_set` (通用布尔切换)
    - 迁移与去重相关的规则设置 `dedup_settings`, `update_rule_dedup`
- [ ] **迁移关键词与替换 (keywords.py)**
    - 迁移 `keywords`, `add_keyword`, `clear_keywords`
    - 迁移 `replaces`, `add_replace`, `clear_replaces`

### 组 C: 复杂逻辑与监控 (Key: `session.py`, `analytics.py`)
- [ ] **迁移会话管理 (session.py)**
    - 迁移 `session_management`, `delete_session_messages`系列
    - 迁移 `session_dedup` 系列 (扫描、删除重复)
    - 迁移时间选择器相关逻辑 (`time_range_selection`, `set_time` 等)
- [ ] **迁移数据分析 (analytics.py)**
    - 迁移 `detailed_analytics`, `realtime_monitor`
    - 迁移 `db_performance_monitor`, `db_optimization_center`
    - 迁移 `forward_stats_detailed`

### 组 D: 新增特性 (Key: `multi_source.py`)
- [ ] **迁移多源管理 (multi_source.py)**
    - 迁移 `multi_source_management`, `manage_multi_source`
    - 迁移 `rule_status`, `sync_config`

## 第三阶段：清理与收尾 (Phase 3: Cleanup)
- [ ] **全量验证**
    - 逐一测试主菜单、规则管理、系统设置等核心流程
    - 检查日志是否有由 Dispatcher 处理的记录
- [ ] **代码清理**
    - 删除 `new_menu_callback.py` 中已迁移的遗留代码
    - 确保 `new_menu_callback.py` 仅作为入口薄层
- [ ] **集成测试**
    - 运行 `pytest` 确保重构未破坏现有功能
- [ ] **文档更新**
    - 更新 `process.md` 标记任务完成
