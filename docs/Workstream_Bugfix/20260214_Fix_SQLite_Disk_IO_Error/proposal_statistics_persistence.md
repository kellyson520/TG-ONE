
# 技术方案：轻量级统计数据持久化 (Statistics Persistence Proposal)

## 1. 核心问题与目标
*   **问题**：为了解决 SQLite I/O 问题，我们实施了自动清理机制，导致数据库中的历史数据（已完成/已失败任务）会被定期物理删除。
*   **目标**：在数据被物理删除前，将其统计信息（计数、时间范围等）持久化到磁盘，以便用户随时查看“自部署以来处理的总消息量”。

## 2. 架构设计：冷热分离统计 (Hot/Cold Stats)

参考业界成熟的 LSM-Tree (Log-Structured Merge-tree) 思想，我们采用 **“实时查询 + 归档累加”** 的策略，避免高频写磁盘。

*   **热数据 (Hot Data)**: 存储在 SQLite 数据库中。
    *   获取方式: `SELECT COUNT(*) FROM task_queue`
*   **冷数据 (Cold Data)**: 存储在 JSON 文件中。
    *   获取方式: 读取 JSON 文件中的 `accumulated_counts` 字段。
*   **总数据 (Total)**: `Hot Data` + `Cold Data`。

### 2.1 存储设计
*   **文件路径**: `./data/stats/lifetime_stats.json`
*   **数据结构**:
    ```json
    {
      "meta": {
        "version": "1.0",
        "last_updated": "2026-02-14T15:30:00",
        "deployment_start_date": "2026-01-01T00:00:00"
      },
      "lifetime_totals": {
        "total_tasks_processed": 150000,  // 归档累加值
        "total_tasks_failed": 5000,
        "total_logs_cleaned": 200000
      },
      "cleanup_history": [  // 最近 10 次清理记录（审计用）
        {
          "date": "2026-02-14T15:30:00",
          "cleaned_tasks": 10000,
          "cleaned_logs": 5000,
          "reason": "maintenance_cron"
        }
      ]
    }
    ```

## 3. 磁盘写入策略 (Disk I/O Strategy)

为了杜绝文件损坏和 I/O 阻塞（吸取之前的教训），我们采用 **原子写入 (Atomic Write)** 模式。

### 3.1 写入流程 (The Safe-Write Protocol)
1.  **准备数据**: 在内存中构建完整的 JSON 对象。
2.  **写入临时文件**: 将数据写入 `lifetime_stats.json.tmp`。
    *   **Buffer**: 使用 buffer 写入，减少系统调用。
    *   **Flush & Fsync**: 写入完成后，强制调用 `os.fsync()` 确保数据刷入物理磁盘（防止断电丢数据）。
3.  **原子替换**: 使用 `os.replace(tmp_file, target_file)`。
    *   在 POSIX (Linux) 和 Windows (Python 3.3+) 上，这是原子操作。
    *   要么成功替换，要么保留原文件，**绝不会出现文件内容写了一半的情况**。

### 3.2 触发时机
我们**不需要**实时写入，只要在以下时刻触发：
1.  **执行数据库清理时** (`cleanup_old_logs`)：这是数据从热变冷的唯一时刻。
2.  **系统关闭时** (可选)：作为额外保险。

由于 `cleanup_old_logs` 频率很低（通常每天或每小时一次），这种方案对磁盘 I/O 的压力几乎为 **零**。

## 4. 代码实现接入点

### 修改 `core/db_factory.py`

在 `async_cleanup_old_logs` 方法中，在执行 `DELETE` 之前，先统计即将删除的行数，然后调用 `StatsManager.increment(...)`。

```python
# 伪代码示例
async def async_cleanup_old_logs(days: int):
    # 1. 统计即将删除的数据
    count = await session.execute(select(func.count()).where(...))
    
    # 2. 执行删除
    await session.execute(delete(...))
    
    # 3. 归档统计 (原子写入 JSON)
    StatsManager.record_cleanup(tasks_removed=count)
```

## 5. 审核点 (Checklist)

*   [ ] **数据完整性**: 使用 `os.replace` 确保原子性。
*   [ ] **性能影响**: 仅在清理时触发写入（低频），无性能损耗。
*   [ ] **并发安全**: 统计文件操作由单线程（维护任务）控制，或使用简单的文件锁（如果多进程）。
*   [ ] **可读性**: JSON 格式，人类可读，方便调试。

请审核此方案。如果通过，我将开始实现 `StatsManager` 并将其集成到清理流程中。
