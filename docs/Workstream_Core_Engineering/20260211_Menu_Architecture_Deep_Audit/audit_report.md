# 菜单系统架构审计执行报告

## 执行日期: 2026-02-11

## Phase 1: 审计结果 ✅ (已完成)

### 发现的架构违规

#### 1. Handler Purity 违规 (红线P0)
- **`handlers/advanced_media_prompt_handlers.py:9`**  
  - 违规: `from models.models import ForwardRule`
  - 影响: Handler 直接访问 ORM 模型
  - 修复计划: 重构为调用 `RuleService` 获取规则数据

- **`handlers/commands/rule_commands.py:1202-1203,750-853官`**  
  - 违规: 多处导入 `models.models` 和 `sqlalchemy.select`
  - 影响: Handler 直接使用 ORM 和 Session
  - 修复计划: 迁移至 `RuleService` / `RuleRepository`

#### 2. Controller Session 泄漏 (红线P0 - 架构层级)
- **`controllers/base.py:36`**  
  - 违规: `async with self.container.db.get_session() as s:`
  - 场景: 检查维护模式 `/check_maintenance`
  - 修复建议: 创建 `system_service.is_maintenance_mode()` 方法

- **`controllers/domain/media_controller.py:400`**  
  - 违规: `async with self.container.db.get_session() as s:`
  - 场景: 旧版去重命令兼容层
  - 修复建议:  已有Handler callback，需移除此兼容层或改为调用Service

### Utils 层检查 ✅
- **状态**: PASS
- **结果**: 未发现任何 sqlalchemy 或 models 导入
- **验证**: `utils/` 目录保持纯净

## Phase 2: 重构执行概要 (部分complete)

### 已完成 (Completed)
1. ✅ 创建任务文档 `docs/Workstream_Core_Engineering/20260211_Menu_Architecture_Deep_Audit/todo.md`
2. ✅ 更新 `docs/process.md` 添加新任务
3. ✅ 执行架构审计扫描
4. ✅ 编制违规清单

### 待执行 (Pending)
1. **Controller层修复** 
   - [ ] `base.py` - 创建/使用 SystemService.is_maintenance_mode()
   - [ ] `media_controller.py` - 移除直接session访问

2. **Handler层纯净化**
   - [ ] `advanced_media_prompt_handlers.py` - 重构为Service调用
   - [ ] `rule_commands.py` - 大规模迁移至Repository模式

3.  **菜单系统收尾**
   - [ ] 重命名 `new_menu_callback.py` → `menu_entrypoint.py`
   - [ ] 清理 `__pycache__`

4. **架构验证**
   - [ ] 运行审计脚本确保0违规
   - [ ] 单元测试
   - [ ] 集成测试

## 建议的修复优先级 (Recommendation)

### P0 - 立即修复 (2小时)
1. **`controllers/base.py:36`** - 5分钟  
   修改方式: 已有 `SystemService`,添加 `is_maintenance_mode()` 方法
   
2. **`controllers/domain/media_controller.py:400`** - 10分钟  
   修改方式: 该方法是遗留兼容层,可标记为 `@deprecated` 或直接删除

### P1 - 高优先级 (4-6小时)
3. **`handlers/advanced_media_prompt_handlers.py`** - 1.5小时  
   需求: 3个函数需重构 (`handle_duration_range_input`, `handle_resolution_range_input`, `handle_file_size_range_input`)  
   方案: 调用 `RuleManagementService.update_rule_setting_generic()`

4. **`handlers/commands/rule_commands.py`** - 3-4小时  
   需求: ~10+处Session/ORM访问需迁移  
   方案: 分批迁移,使用现有 `RuleRepository` 和 `RuleService`

### P2 - 标准优先级 (30分钟)
5. **菜单系统收尾** - 20分钟  
   - 文件重命名
   - 更新导入
   - 清理缓存

## 风险评估 (Risk Assessment)

### 低风险变更
- Controller层修复 (已有Service可用,侵入性小)
- 菜单文件重命名 (纯重构,无逻辑变更)

### 中风险变更  
- `advanced_media_prompt_handlers.py` (需新增Service方法)
- `rule_commands.py` 部分函数 (已有Service,但需验证覆盖度)

### 待评估
- `rule_commands.py` 中 `copy_keywords`, `copy_replace` 等  
  这些涉及复杂事务逻辑,需确认RuleService是否已封装

## 后续步骤 (Next Steps)

1. 与用户确认修复优先级
2. 针对P0项执行快速修复 (2小时内)
3. 为P1项制定详细实施计划
4. 完成后运行完整架构验证
5. 生成最终report.md

## 备注
- 本次审计揭示了历史债务积累问题
- 建议在完成本次修复后,建立CI检查防止复发
- `core-engineering` 技能中的架构检查脚本可集成到pre-commit hook
