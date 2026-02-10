# 任务清单: 完美异步退出与全状态自愈架构 (Todo List)

## 状态总览
- [ ] 阶段 1: 任务追踪与注册表升级 (Registry) ⏳
- [ ] 阶段 2: 核心生命周期与手动 Loop 管理 (Manual Loop) ⏳
- [ ] 阶段 3: 组件级精准清理 (Service Clean) ⏳
- [ ] 阶段 4: 诊断透明化与可观测性 (Diagnostics) ⏳
- [ ] 阶段 5: 测试验证与物理兜底 (Verification) ⏳

---

## 详细子任务

### 1. 任务追踪与注册表升级
- [x] 在 `exception_handler.py` 中引入 `weakref.WeakSet` 用于自动追踪活跃任务。
- [x] 升级 `create_task` 接口，实现任务创建时的自动入库与引用管理。
- [x] 开发 `cancel_all_managed_tasks()` 接口，支持批量取消及 `asyncio.gather` 等待。
- [x] 实现任务分类标注（Critical / Non-Critical）。
- [x] 增加 `get_active_tasks_inventory()` 函数，统计未关闭任务名单。
- [x] 为注册任务增加超时自动管理机制 (集成在取消流程中)。

### 2. 核心生命周期与手动 Loop 管理
- [x] 重构 `main.py`，弃用 `asyncio.run`，改用手动 `new_event_loop` 管理。
- [x] 显式调用 `loop.shutdown_asyncgens()` 清理异步生成器。
- [x] 实施 `loop.shutdown_default_executor()` 强制关闭线程池（解决 DB 驱动阻塞）。
- [x] 定义 `ManualTeardownSequence` 清理序列 (已在 main.py finally 块实现)。
- [x] 实现自定义 `Loop Exception Handler` 减少退出噪音。
- [x] 确保 `loop.close()` 在所有资源释放后执行。

### 3. 组件级精准清理
- [x] 为 `TelegramClient.disconnect()` 增加强制超时包装 (4s)。
- [x] 更新 `UpdateService` 后台任务适配任务注册表。
- [x] 优化 `Database` 销毁逻辑 (通过 dispose 确定性关闭)。
- [x] 实现 `Pre-Shutdown Broadcast` 预清理指令 (SYSTEM_SHUTDOWN_STARTING)。
- [x] 缩短 `SleepManager` 对 `CancelledError` 的感知步长 (60s -> 5s)。
- [ ] 确保文件系统原子操作在进程退出前刷盘。

### 4. 诊断透明化与可观测性
- [x] 开发 `dump_stubborn_tasks()` 工具抓取顽固任务堆栈。
- [x] 实现“退出进度条”式日志输出 (Shutdown 1/4...4/4)。
- [x] 增加性能分析，实现退出耗时统计并输出到日志。
- [x] 实现调试模式下的“人工挂起检查”开关 (DEBUG_SHUTDOWN_HANG=1)。
- [x] 为 `log_push` 增加临终上报功能 (已集成在整体退出日志中)。
- [x] 记录详细退出诱因 (已集成在 main / lifecycle 日志中)。

### 5. 测试验证与物理兜底
- [x] 编写 `unit/test_task_tracking.py` 验证任务追踪与清理。
- [x] 验证顽固任务的诊断输出逻辑。
- [x] 跨平台逻辑审计 (已确保在 Win/Linux 下一致性)。
- [x] 重构 `os._exit` 逻辑作为 T+40s 的终极物理熔断器。
- [x] 审计各组件对 `CancelledError` 的处理。
- [x] 执行更新模拟测试，验证退出并触发更新的流畅度。
