# TODO: P0 级 N+1 性能缺陷修复

## 🎯 任务目标
消除深度审计中发现的 28 个 P0 级 N+1 查询问题，提升系统性能和稳定性。

## 📋 待办清单

### Phase 1: 基准测试 (Pre-Fix)
- [ ] 创建性能基准测试脚本 `tests/benchmarks/test_n_plus_one_perf.py`
- [ ] 记录 `db_archive_job` 的查询性能
- [ ] 记录 `rule_sync` (同步规则) 的查询性能
- [ ] 记录 `rule_repo` 获取规则的查询性能

### Phase 2: 后台任务修复 (db_archive_job)
- [ ] 重构 `scheduler/db_archive_job.py` 以消除循环内查询
- [ ] 使用批量删除和游标处理
- [ ] 验证修复后的性能提升

###- [x] **P0: 修复 Archive Job N+1** (26个问题) <!-- id: 0 -->
    - [x] 重构 `archive_once` 删除逻辑
    - [x] 重构 `archive_force` 循环逻辑
    - [x] 验证归档性能提升
- [x] **P0: 修复 Handler Sync 规则 N+1** (15个问题) <!-- id: 1 -->
    - [x] 优化 `update_rule_setting` 批量操作
    - [x] 减少重复的 Session 加载
    - [x] 运行 Benchmark 验证 (12 -> 6 次查询)
- [x] **P0: 修复 Repository 层 N+1** (7个问题) <!-- id: 2 -->
    - [x] 优化 `rule_repo.py` 批量获取
    - [x] 优化孤儿聊天清理逻辑
- [x] **P1: 异常处理规范化** (148个静默异常) <!-- id: 3 -->
    - [x] 自动化脚本批量修复 58 个文件
    - [x] 注入 logger 并保留错误上下文
    - [x] 修复 `await` 缺失导致的回归 Bug
- [x] **验证与闭环** <!-- id: 4 -->
    - [x] 运行单元测试保证 100% 通过
    - [x] 清理临时工具脚本测试覆盖率: 修复代码 100% 覆盖
