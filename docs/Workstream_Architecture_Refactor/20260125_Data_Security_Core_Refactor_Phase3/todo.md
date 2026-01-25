# Task List: Phase 3 Data Security Core Refactor

## 模块一：Handler 层彻底收敛 [100% DONE] ✅
- [x] 分离 `handlers/command_handlers.py` 为具体命令文件
- [x] 更新 `bot.py` 路由
- [x] 验证命令路由逻辑一致性

## 模块二：Service 层数据库解耦 [100% DONE] ✅
- [x] 重构 `services/rule/logic.py`: 移除所有 `db.session` 直接调用
- [x] 完善 `RuleRepository`: 增加 `get_full_rule_orm`, `save_rule_orm`, `delete_all_rules` 等底层方法
- [x] 实现 `RuleLogicService.cleanup_orphan_chats`

## 模块三：Utils 层清理 [100% DONE] ✅
- [x] 重构 `utils/helpers/common.py`: `is_admin` 移除数据库硬编码逻辑
- [x] 重构 `check_and_clean_chats`: 移除硬编码 SQL/Session 调用，改用 Service + Repo 模式

## 模块四：模型物理拆分 [100% DONE] ✅
- [x] 将 `models/models.py` 拆分为模块化结构 (Chat, Rule, User, Stats, System, Dedup, Migration)
- [x] 建立 `models/__init__.py` 维护全局导出
- [x] `models/models.py` 切换为兼容性 Proxy

## 下一步计划
- [ ] 运行基本功能验证 (P3 Verify)
- [ ] 准备进行 Phase 5 (Alembic 数据库迁移)
