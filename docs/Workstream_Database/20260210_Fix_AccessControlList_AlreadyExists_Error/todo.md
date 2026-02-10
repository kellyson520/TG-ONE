# 修复 access_control_list 表已存在错误 (20260210)

## 背景 (Context)
系统在启动或执行数据库初始化时，抛出 `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) table access_control_list already exists`。
这通常是因为 `CREATE TABLE` 语句在表已存在时未加 `IF NOT EXISTS` 判断，或者 SQLAlchemy 的自动建表逻辑与现有表冲突。

## 待办清单 (Checklist)

### Phase 1: 问题诊断 (Diagnosis)
- [x] 定位抛出该错误的具体代码位置 (`core/db_init.py` & `models/migration.py`)
- [x] 检查 `access_control_list` 的定义与现有数据库结构的一致性 (两者一致)
- [x] 确认是否是 Alembic 迁移与手动 `create_all` 的冲突 (多重初始化路径 & 路径解析差异)

### Phase 2: 修复实施 (Build)
- [x] 修正 `models/migration.py` 使用小写 table name 检查并添加 `checkfirst=True`
- [x] 确保 `core/db_init.py` 同步引擎使用绝对路径以避免多数据库文件冲突
- [x] 修正 `core/db_init.py` 的重复日志并在 `create_all` 中显式传递 `checkfirst=True`
- [ ] 验证修复后的启动流程

### Phase 3: 验证与验收 (Verify)
- [x] 运行 `python -m core.db_init` 确保不再报错
- [x] 验证 `access_control_list` 表已存在于 `forward.db` 中
- [x] 手动检查 Alembic 状态
- [x] 提交任务报告
