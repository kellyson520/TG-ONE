# 技术方案: 完美异步退出与全状态自愈架构 (Perfect Shutdown Architecture)

## 1. 背景与问题分析
当前系统在执行更新或正常退出时，偶尔会出现“日志显示 Shutdown Complete 但进程不消失”的现象。
- **根因**: `asyncio.run()` 是一个黑盒，无法清理卡在底层线程池（Executor）或未追踪的异步任务。
- **现状**: 采用 `os._exit()` 虽能强行解决更新问题，但不够优雅，且无法在退出时获取诊断信息。

## 2. 设计目标
- 实现 **100% 确定性** 的异步退出。
- 提供退出阶段的 **全透明诊断**（如果挂起，必须知道卡在哪里）。
- 确保所有三方库（Telethon, SQLAlchemy）资源被物理释放。

## 3. 核心设计说明

### 3.1 任务管家 (Task Registry)
在 `GlobalExceptionHandler` 中引入基于 `weakref.WeakSet` 的任务追踪器。
- 所有通过系统接口创建的任务将被自动记录。
- 退出时支持 `cancel_all_managed_tasks()` 批量清理。

### 3.2 拆解 Event Loop 清理阶段
弃用 `asyncio.run`，在 `main.py` 中实施以下手动清理序列：
1. **取消业务任务**: 发送 Cancel 信号并等待。
2. **销毁异步生成器**: 调用 `loop.shutdown_asyncgens()`。
3. **关闭线程池**: 调用 `loop.shutdown_default_executor()`。
4. **关闭循环**: 最后执行 `loop.close()`。

### 3.3 自愈与超时管理
- 建立 30 秒“优雅清理窗口”。
- T+30s: 触发 `dump_stubborn_tasks()` 捕获挂起点的堆栈。
- T+40s: 物理熔断器 (`os._exit`) 介入。

## 4. 架构影响评估
- **侵入性**: 中等。需修改 `main.py` 及 `exception_handler.py`。
- **性能**: 无负面影响。
- **稳定性**: 极大提升更新成功率及容器环境下的稳定性。
