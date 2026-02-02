# 任务：修复任务重复获取问题 (Fix Duplicate Task Fetching)

## 问题描述
用户反馈系统日志中出现任务 ID 虽然不同但处理的消息内容相同的情况（如 Task 90 和 91 都在处理 ID=2369852 的消息），导致重复转发。

## 根因分析
1. **数据库约束缺失**：`task_queue` 表的 `unique_key` 虽然在模型中定义了 `unique=True`，但实际数据库中并未生效（SQLite 迁移问题），导致相同消息产生了多个 Task。
2. **并发竞争 (Race Condition)**：多个 Worker 同时调用 `fetch_next()`，虽然单个 Task 的拉取是原子的，但媒体组 (Media Group) 的聚合逻辑是在拉取后进行的。如果两个 Worker 分别拉取了属于同一组的两个不同 Task，它们会各自独立处理，造成重复。
3. **完成状态同步缺失**：Worker 在处理完一个媒体组后，只完成了 main_task，没有同步完成 group_tasks。

## 解决策略
- [x] **Phase 1: 数据库强化 (Diagnosis & Implementation)**
    - [x] 强制在 `migrate_db` 中将 `unique_key` 索引升级为 `UNIQUE INDEX`。
    - [x] 在创建唯一索引前添加重复数据清理逻辑。
- [x] **Phase 2: 逻辑闭环 (Implementation)**
    - [x] 修改 `TaskRepository.push` 使用 `INSERT OR IGNORE` 确保入库幂等性。
    - [x] 修改 `TaskRepository.fetch_next` 为**组原子拉取**：一次性拉取并锁定整个媒体组的所有 Pending 任务。
    - [x] 更新 `WorkerService`：
        - [x] 适配 `fetch_next` 返回的任务列表。
        - [x] 任务成功/失败时同步更新组内所有任务的状态。
- [x] **Phase 3: 验证 (Verification)**
    - [x] 运行数据库迁移脚本，确认 UNIQUE 约束生效。
    - [x] 代码静态审查，确认多 Worker 竞争窗口已关闭。

## 交付产物
- `models/migration.py`: 增强版索引迁移逻辑。
- `repositories/task_repo.py`: 原子化组拉取逻辑。
- `services/worker_service.py`: 组任务状态管理逻辑。
 `report.md`
