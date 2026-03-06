# TODO: Hotword IO Optimization

## Phase 1: Plan (方案规划与确认)
- [x] 创建任务文件夹与 spec.md
- [x] 评审并发控制参数 (Semaphore 建议值: 10)
- [x] 决定采取方案 B (SQLite 核心存储)

## Phase 2: Setup (环境预检)
- [x] 配置 `HOT_DB_PATH` 与 `HOT_DATABASE_URL`
- [x] 创建 `models/hotword.py` 数据库模型
- [x] 编写 `services/hotword_db_init.py` 初始化逻辑

## Phase 3: Build (代码重构)
- [x] **HotwordRepository**: 完全重构，支持异步 UPSERT 与 归档 SQL
- [x] **HotwordService**:
    - [x] 引入 `io_semaphore` 并发控制
    - [x] `aggregate_daily` 迁移至 DB 事务逻辑
    - [x] `get_rankings` 异步化改造
- [x] **Handlers**: 适配异步指令与回调

## Phase 4: Verify (验证与门禁)
- [x] 运行模拟批量频道生成的 IO 压测脚本 (集成测试通过)
- [x] 检查 `iowait` 监控指标 (基准稳定)
- [x] 验证文件重命名的原子性 (已通过 DB 事务原子性替代)

## Phase 5: Report (报告与归档)
- [x] 迁移旧 JSON 配置至数据库并移除 `data/hot/` 目录
- [x] 清理 `HotwordService` 与 `Repository` 中的冗余导入与同步代码
- [x] 生成性能对比报告 (集成测试验证 IO 削峰有效)
- [x] 归档 Workstream
