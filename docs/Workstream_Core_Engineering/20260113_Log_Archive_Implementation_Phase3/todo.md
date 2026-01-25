# Log Archive Implementation (Phase 3)

## 任务说明
定期将旧数据移出主库（forward.db），保持轻量，并与原先项目的冷存储功能衔接。

## 技术规范
- **归档目标表**: `rule_logs`, `rule_statistics`, `chat_statistics`, `error_logs`, `media_signatures`, `task_queue`
- **存储格式**: Parquet (DuckDB 兼容)
- **分区策略**: 按年/月/日分区
- **保留策略**: 主库保留 30 天，其余移至 Parquet 冷存储
- **检索方式**: 支持从 Parquet 文件检索历史记录

## 待办事项
- [ ] 初始化归档目录结构 `archive/parquet` 和 `archive/bloom`
- [ ] 实现 `ArchiveManager` 类负责调度归档逻辑
- [ ] 增强 `db_operations.py` 以支持归档后的数据清理
- [ ] 实现增量归档逻辑（仅归档未归档的数据）
- [ ] 集成冷存储查询接口到 Web UI API
- [ ] 编写单元测试验证归档和恢复逻辑
- [ ] 更新系统启动脚本以包含定期归档任务

## 进度记录
- 2026-01-13: 任务初始化，开始方案设计
