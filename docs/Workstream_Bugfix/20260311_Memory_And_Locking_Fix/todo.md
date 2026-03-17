# 内存危机恢复与资源竞态自愈优化 (Intelligent Memory & Locking Refactor)

## 背景 (Context)
系统出现持续卡死问题，触发 `⚠️ [ResourceGuard] 内存仍处于危机状态`。并发量增加导致 `会话处理失败` 与 `任务状态不匹配`。原计划采用"一刀切"的日志降级和强切分发器，未能从根本上提升系统在高压下的健壮性，且对排查可能造成阻碍。我们需要智能化、动态化、可靠且低占用的解决方案。

## 待办清单 (Checklist)

### Phase 1: 动态水位线与平滑恢复机制 (Dynamic Memory Control & Soft Recovery)
- [x] **引入多级动态水位调控**: 在 `services/worker_service.py` 中废除机械的 `stop/start` 启停逻辑。引入阶段性水位线 (Warning/Critical/Fatal)。复用 `TaskDispatcher` 已有的 `_adaptive_sleep` 抖动退避思维，在达到高水位时直接动态调大 `current_sleep`，实现降速而非直接掐断停机 (Soft-Start 亦可通过自动回调重置休眠来实现)。
- [x] **自适应分代回收 (Adaptive GC)**: 优化 ResourceGuard 里的 GC 调用，根据监控周期的内存上升率选择轻量分代回收 `gc.collect(1)` 与全局回收的使用时机，减弱 GC 时造成的 CPU 毛刺卡顿。

### Phase 2: 锁竞态自适应重试与乐观协调 (Lock Contention Healing)
- [x] **SQLite 指数退避重试 (Exponential Backoff)**: 完善 `core/database.py`，复用同款带有随机抖动因子的指数退避重试算法 (Jitter Exponential Backoff) 去拦截处理 `OperationalError: database is locked` 的写入竞争，避免直接报错，提升实际成单率并减少高压抛错。
- [x] **状态流转 CAS (Compare-And-Swap) 乐观锁**: 重修 `repositories/task_repo.py`。如果 `complete` / `fail` 出现状态失配，不再统一报 ERROR。利用状态查询做复检，对合法的时序交错（例如超时自动救援又被旧 Worker 提交）做静默处理或安全降级为 DEBUG/WARNING。
