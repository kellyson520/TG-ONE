# 数据库事务与唯一约束错误修复报告 (Fix Database Transaction and Integrity Errors)

## 摘要 (Summary)
修复了数据库维护操作（VACUUM）因事务冲突导致的失败，以及媒体签名记录（MediaSignature）并发写入时的唯一约束冲突问题。

## 问题详情与解决方案 (Details)

### 1. VACUUM 事务冲突修复
- **问题**: SQLite `VACUUM` 指令不能在事务内部运行。异步模式下的 `async_vacuum_database` 未显式设置 Autocommit 模式，导致 SQLAlchemy/aiosqlite 隐式开启事务并报错。
- **解决**: 在 `core/db_factory.py` 中，为 `VACUUM` 操作显式配置 `isolation_level="AUTOCOMMIT"`，确保其在事务外运行。

### 2. MediaSignature 唯一约束冲突修复
- **问题**: 
    1. 在 `GroupCommitCoordinator` 中，批量写入（add_all）时如果包含重复记录，会导致整个批次失败并回滚。
    2. `MediaSignature` 在 Group Commit 模式下创建时缺少时间戳，导致审计信息不完整。
- **解决**:
    - **弹性增强**: 修改 `services/db_buffer.py` 中的 `GroupCommitCoordinator._flush`。当 `add_all` 因 `IntegrityError` 失败时，自动切换至**逐条处理模式**。逐条处理时，成功的记录会被提交，而冲突的记录将被记录并跳过。
    - **元数据补全**: 在 `services/dedup_service.py` 中，为通过 Group Commit 提交的 `MediaSignature` 对象预先填充 `created_at`、`updated_at`、`last_seen` 和 `count` 默认值。

## 验证 (Verification)
- **单元测试**: 创建并运行了 `test_db_buffer_resilience.py`，模拟了 Group Commit 中的重复写入场景。
- **结果**: 测试确认在批次中存在重复记录时，正常记录依然能够成功持久化，且系统不再抛出未捕获的 `IntegrityError`。
- **日志验证**: fallover 机制工作正常，日志中记录了预期的回滚和重试信息。

## 影响范围 (Impact)
- 提升了数据库自动维护的成功率。
- 极大地增强了高并发消息流下的媒体去重稳定性，避免了因单条冲突导致的一系列记录丢失。
