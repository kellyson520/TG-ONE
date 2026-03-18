# 归档管理器数据库锁死修复方案 (Spec)

## 背景 (Context)
归档周期(`run_archiving_cycle`)中的 `archive_model_data` 核心任务在查询旧数据总量时遭遇 `database is locked`：
```python
            count_stmt = select(func.count()).select_from(model).where(
                time_column < cutoff_date
            )
            result = await session.execute(count_stmt)
```
后方的 Fetching 和 Deleting 两个阶段均设计了 `max_retries = 5` 的重试指数回退。唯独第一阶段没有重试，导致整个周期崩溃。

## 解决方案 (Solution)

### 1. 调整引入位置
将 `import asyncio` 和 `from sqlalchemy.exc import OperationalError` 统一调整到 `archive_model_data` 函数最前端或模块顶端。

### 2. 为 $Count(*)$ 增加重试逻辑
使用与 Fetching/Deleting 对齐的重试逻辑保护 `session.execute(count_stmt)`。

```python
            max_retries = 5
            retry_delay = 1.0
            
            count = 0
            for attempt in range(max_retries):
                try:
                    count_stmt = select(func.count()).select_from(model).where(
                        time_column < cutoff_date
                    )
                    result = await session.execute(count_stmt)
                    count = result.scalar()
                    break
                except OperationalError as oe:
                    if "locked" in str(oe).lower() and attempt < max_retries - 1:
                        logger.warning(f"查询 {table_name} 待归档记录数时遭遇数据库锁定 (尝试 {attempt+1}/{max_retries}): {oe}. 正在重试...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise
```

## 风险评估与控制 (Risk & Mitigation)
- **回退策略**: 采用原有 1.0s, 2.0s, 4.0s ... 的指数回退配置，最大重试次数 5 次。
- **并发控制**: Archiving 周期默认已经设计了互斥锁 (`self.is_running`)，确保不会同时有多个 Archiving 并行，主要的阻挡是外部的高频并发写入模块。
