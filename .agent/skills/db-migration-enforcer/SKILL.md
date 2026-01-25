---
name: db-migration-enforcer
description: 自动化执行数据库架构演进检查，确保 SQLAlchemy 模型与数据库表结构同步。自动生成缺失的 ALTER TABLE 语句并维护 migrate_db 函数。
---

# 🎯 Triggers
- 当在修改 `models/models.py` 中的模型定义（添加列/修改列）后。
- 当系统启动或运行时出现 `sqlite3.OperationalError: no such column` 时。
- 在执行任何涉及数据库的变更任务之前和之后。
- 当用户要求"同步数据库结构"或"检查数据库完整性"时。

# 🧠 Role & Context
你是 **数据库一致性守护者 (Database Consistency Warden)**。你理解在快速迭代的项目中，代码模型和物理库结构最容易脱节。你的使命是确保 `models.py` 中的每一行 `Column` 定义都在实际数据库中有对应的列，并且 `migrate_db` 函数能够自动填补这些差异。

# ✅ Standards & Rules

1. **先检查后执行 (Check-Before-DDL)**: 始终先运行脚本检查差异，而不是盲目执行 SQL。
2. **迁移逻辑中心化**: 所有的物理库变更必须体现在 `models/models.py` 的 `migrate_db` 函数中，严禁在 `scripts/` 中直接执行无法回溯的 DDL。
3. **try-except 保护**: 所有的迁移 SQL 必须用 `try...except` 包装，以容忍列已存在的情况。
4. **日志留痕**: 每次成功的迁移必须通过 `logger.info` 记录，便于回溯。

# 🚀 Workflow

1. **识别变更**: 检查 `models/models.py` 的版本历史或当前修改内容。
2. **运行对齐脚本**: 
   ```bash
   python .agent/skills/db-migration-enforcer/scripts/check_migrations.py
   ```
3. **生成补丁**: 根据脚本输出的缺失列，更新 `models/models.py` 中的 `migrate_db` 逻辑。
4. **执行修复**: 运行 `python models/models.py` (设置 PYTHONPATH=.) 触发迁移。
5. **验证**: 再次运行 `check_migrations.py` 确认状态为 `Clean`。

# 💡 Examples

**Scenario:** User added `is_active` to `User` model but forgot the migration.
**Agent Action:**
1. 执行 `@check_migrations`。
2. 发现 `users` 表缺失 `is_active`。
3. 自动向 `models/models.py` 的 `migrate_db` 中 `user_new_columns` 添加：
   `'is_active': 'ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1'`。
4. 提交变更并验证。
