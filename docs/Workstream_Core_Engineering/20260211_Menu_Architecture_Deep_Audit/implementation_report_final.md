# 架构审计与 Handler Purity 重构报告 (20260211)

## 任务背景
在 2026/02/11 的架构审计中，发现多个 Callback Handler 和 Command Handler 直接导入了 ORM 模型 (`from models.models import ...`) 并直接使用 `sqlalchemy` 执行数据库操作。这违反了 `Standard_Whitepaper.md` 定义的 **Handler Purity** 原则 (Handler 仅负责编排 Service 和 Repository)。

## 修复摘要 (Summary of Fixes)

### 1. Callback Handlers 纯净化 (P0)
对 `handlers/button/callback/` 目录下的所有核心文件进行了彻底重构：
- **`admin_callback.py`**: 移除了对 `LogRecord` 和 `MessageForwardHistory` 的直接查询。系统日志统计、数据库归档中心、推送设置等逻辑全部委派给 `SystemService`。
- **`ai_callback.py`**: 时长总结、AI 模型切换等逻辑迁移至 `RuleManagementService`。
- **`media_callback.py`**: 媒体类型切换、扩展名管理等逻辑迁移至 `MediaService`。
- **`push_callback.py`**: 推送渠道添加/删除逻辑迁移至 `RuleManagementService`。
- **`advanced_media_callback.py`**: 视频分辨率、时长范围、文件大小等高级过滤设置迁移至 `RuleManagementService.toggle_rule_setting`。
- **`other_callback.py`**: 这是一个大型重构，整合了“一键复制”、“全量扫描去重”、“规则汇总”等复杂功能。逻辑全部由 `RuleLogicService` (通过 `RuleManagementService` 代理) 承载。

### 2. Command Handlers 纯净化 (P0)
- **`handlers/commands/rule_commands.py`**: 
  - 重构了 `/copy_keywords` 和 `/copy_replace` 命令。
  - 移除了函数内部的 `SQLAlchemy` 和 `models` 导入。
  - 在 `RuleLogicService` 中新增了 `copy_keywords_from_rule` 和 `copy_replace_rules_from_rule` 方法以支持原子化业务操作。
- **`_get_current_rule_for_chat`**: 移除了显式的 `session` 参数传递，完全由 `RuleQueryService` 内部管理。

### 3. Service 层增强
- **`RuleLogicService`**:
  - 新增 `copy_keywords_from_rule`: 支持从另一个规则复制关键字（支持排除/正则筛选）。
  - 新增 `copy_replace_rules_from_rule`: 支持从另一个规则复制内容替换规则并自动去重。
- **状态管理**: 统一使用 `session_manager` (来自 `services.session_service`) 替代遗留的 `state_manager`。

### 4. 路由与分发优化
- **`callback_handlers.py`**: 补全了对 `handle_generic_toggle` 的路由配置，并确保所有回调均通过 `RadixRouter` 精确分发到对应的模块化处理器。

## 架构合规性验证
通过 `PowerShell` 扫描 `handlers` 目录：
```powershell
Get-ChildItem -Path handlers -Recurse -File | Select-String -Pattern "sqlalchemy|from models"
```
**结果**: 0 处逻辑违规。仅存在于注释中的说明和 `__pycache__` 缓存。

## 验收结果
- [x] Handler 层 0 处直接 ORM 导入 ✅
- [x] Controller 层 0 处 Session 泄漏 ✅
- [x] 业务逻辑 100% 委派至 Service 层 ✅
- [x] 复制、切换、设置等核心功能验证正常 ✅

---
**重构执行人**: Antigravity (Advanced Agentic AI)  
**日期**: 2026-02-11
