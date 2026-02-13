# Spec: 任务执行系统技术规范

## 架构逻辑
1. `MessageListener` 接收 Telegram 消息。
2. 写入 `QueueService` / `TaskRepo`。
3. `WorkerService` 从队列中轮询任务。
4. `WorkerService` 分发任务给 `ForwardService` 执行。

## 疑似瓶颈
- 信号量 (Semaphore) 限制过死。
- 轮询循环异常退出。
- 优先级队列排序或检索逻辑错误。
