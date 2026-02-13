# 任务队列吞吐量优化方案 (Task Queue Optimization Spec)

## 1. 核心问题分析 (Problem Analysis)

### 1.1 伸缩失效 (Scaling Failure)
*   **现象**: `WORKER_MIN_CONCURRENCY` = 2, `WORKER_MAX_CONCURRENCY` = 10, 积压 8.8w, `workers` 实际数 = 2。
*   **疑点**: `_monitor_scaling` 协情可能因异常中断，或 `get_queue_status` 统计的 `pending` 字段与实际 `TaskQueue` 查询不一致。

### 1.2 幽灵负载 (Ghost Load)
*   **现象**: 50% 的失败均为 `Source message not found`。
*   **后果**: 这些任务虽然失败，但依然占用了 fetch -> get_messages -> error -> db_update 的完整生命周期，消耗了大量的 CPU 和网络 IO，拖慢了正常消息的处理。

## 2. 技术方案 (Technical Solutions)

### 2.1 Worker 调度增强
*   **自愈机制**: 在 `WorkerService` 中增加心跳监控。如果 `_monitor_scaling` 停止，由 `Bootstrap` 重新启动。
*   **显式扩容**: 将扩容阈值从 50 修改为更敏感的值，或在启动时直接初始化更多 Worker。

### 2.2 消息预检 (Message Pre-filtering)
*   **死信清理指令**: 
    ```sql
    -- 1. 清理极旧且无意义的积压（如超过2天的待处理任务）
    UPDATE task_queue SET status = 'failed', error_message = 'Expired: System cleanup' 
    WHERE status = 'pending' AND created_at < datetime('now', '-48 hours');
    
    -- 2. 针对已知不存在的消息进行快速标记（防止重复 fetch）
    -- 在代码层面实现，若 get_messages 返回 None，立即 commit 为 failed。
    ```
*   **新旧任务优先级分离**:
    在 `fetch_next` 的 `ORDER BY` 中增加 `created_at DESC`（针对最近任务）或通过两个子查询合并：优先取 15 分钟内的最新任务，其次取带优先级的高权重旧任务。

### 2.3 数据库访问优化
*   **索引加固**: 
    ```sql
    CREATE INDEX idx_task_queue_optim ON task_queue (status, scheduled_at, next_retry_at, priority DESC, created_at ASC);
    ```
*   **原子批量锁定 (Atomic Batch Locking)**:
    修改 `fetch_next` 逻辑，使用 SQLite 的 `LIMIT {batch_size}` 配合 `UPDATE ... RETURNING`。
    ```python
    # 伪代码
    stmt = update(TaskQueue).where(TaskQueue.id.in_(
        select(TaskQueue.id).where(...).limit(5)
    )).values(status='running').returning(TaskQueue)
    ```

## 3. 验证指标 (Metrics)

| 指标 | 目标值 | 计算方式 |
| :--- | :--- | :--- |
| **Running Workers** | 10 | `SELECT count(*) FROM task_queue WHERE status='running'` |
| **有效吞吐率** | > 100 任务/分 | `(Completed_T2 - Completed_T1) / (T2 - T1)` |
| **无效失败比例** | < 10% | `Failed(SourceNotFound) / TotalProcessed` |
| **积压递减率** | 负向增长 | `Pending` 总数持续显著下降 |
