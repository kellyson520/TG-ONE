# 数据库连接池超时问题修复

## 任务概述
修复 `QueuePool limit of size 1 overflow 0 reached, connection timed out` 错误

## 状态
- [x] 问题诊断
- [x] 修复 db_factory.py 写引擎配置
- [x] 修复 database.py 硬编码配置
- [x] 创建修复报告
- [ ] 运行集成测试验证
- [ ] 部署到生产环境
- [ ] 监控错误日志

## 修复详情

### 1. 修复 db_factory.py (已完成)
- **文件**: `core/db_factory.py`
- **行数**: 89-97
- **修改**: 将 `pool_size=1, max_overflow=0` 改为使用 `settings.DB_POOL_SIZE` 和 `settings.DB_MAX_OVERFLOW`

### 2. 修复 database.py (已完成)
- **文件**: `core/database.py`
- **行数**: 28-34
- **修改**: 将硬编码的 `pool_size=20, max_overflow=10` 改为使用 settings 配置

## 验证步骤

### 快速验证
```bash
python -c "from core.db_factory import DbFactory; from core.config import settings; engine = DbFactory.get_async_engine(readonly=False); print(f'Pool Size: {engine.pool.size()}'); print(f'Max Overflow: {engine.pool.overflow()}')"
```

### 集成测试
```bash
pytest tests/unit/repositories/test_task_repo.py -v -k "test_push_batch"
```

### 压力测试（可选）
```bash
pytest tests/performance/test_concurrent_writes.py -v
```

## 预期结果
- ✅ 连接池大小从 1 增加到 20
- ✅ 溢出连接从 0 增加到 30
- ✅ 不再出现 TimeoutError
- ✅ 批量操作性能提升

## 风险评估
- **风险等级**: 低
- **影响范围**: 所有数据库写操作
- **回滚方案**: Git revert 到修复前的提交

## 后续优化建议
1. 监控连接池使用率
2. 考虑实施连接池预热
3. 评估是否需要迁移到 PostgreSQL
