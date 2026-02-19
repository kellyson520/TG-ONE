# 任务报告 (Report): VPS 高负载 (300%) 修复与并发优化

## 1. 任务背景 (Background)
用户反馈在 VPS 上运行时 CPU 负载达到 300%。
经诊断发现：
*   `WorkerService` 扩容算法过度激进（积压量级大时无视资源状态扩至 40 并发）。
*   每个 Worker 同时锁定 10 个任务，导致数据库 `running` 状态虚高（一度达到 200+），诱发严重的 `database is locked` 冲突与重试。
*   API 实体获取逻辑在高频失败时产生大量 `Warning` 日志，且未让出控制权。

## 2. 核心优化项 (Core Optimizations)

### 2.1 WorkerService 智能化伸缩 (`services/worker_service.py`)
*   **资源保护哨兵**：在扩容前增加对 `CPU (<80%)`、`LoadAvg (<1.2x CPU)` 和 `RAM (<1.5GB)` 的强制校验。
*   **保守扩容步长**：将单次扩容最大步长从 5 降至 **3**，增加监控稳定性。
*   **紧急过载保护**：当 CPU > 95% 或负载严重超标时，主动触发即时缩容，强制释放系统资源。
*   **并发状态纠偏**：将 `fetch_next` 的拉取限制从 10 调整为 **1**。确保 `running` 状态任务数严格对应活跃 Worker 数，消除了假性并发积压。

### 2.2 僵尸任务救援机制
*   在 `WorkerService` 启动及运行中（每分钟）新增 `rescue_stuck_tasks` 逻辑。
*   自动清理并在 15-20 分钟内未更新的 `running` 任务重置为 `pending`，防止数据库状态泄露。

### 2.3 API 性能与日志优化 (`services/network/api_optimization.py`)
*   **日志降噪**：将高频发生的“用户实体获取临时失败”预警级别从 `Warning` 降级为 `Debug`，减少高负载下的 IO 负担。
*   **控制权释放**：在实体解析循环中加入 `asyncio.sleep(0.01)`，确保在大规模解析任务中不会长时间阻塞事件循环。

### 2.4 架构分层维护
*   **修复违规**：解决了 `repositories/backup.py` 向上依赖 `services` 的架构违规问题。
*   **重构路径**：将 legacy 备份桥接逻辑迁移至 `services/legacy_backup_bridge.py`。

## 3. 质量门禁验证 (Verification)
*   **Local CI**: 已通过 `Arch Guard` (0 违规) 和 `Flake8 Critical` (0 错误) 检查。
*   **任务状态分析**：通过调整 `limit=1`，已成功解决数据库中 `running` 数量不受限制（200+）的逻辑漏洞。

## 4. 结论与建议 (Conclusion)
*   **当前状态**：优化已部署至代码库，准备推送。
*   **建议建议**：重启后观察系统负载。如果 CPU 仍有压力，可考虑进一步将 `.env` 中的 `WORKER_MAX_CONCURRENCY` 调低至 10。

Implementation Plan, Task List and Thought in Chinese
