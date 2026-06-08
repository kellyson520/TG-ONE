# 任务交付报告: 更新失效与退出挂起深度修复

## 1. 故障总结
在 2026-02-10 12:00 的更新尝试中，系统虽成功触发关闭流程，但在输出 `System shutdown complete.` 后彻底挂起，导致守护进程无法接管执行代码更新。

## 2. 根因分析 (Post-Mortem)
1. **异步泄漏 (Async Leak)**: 包括 `SleepManager` 监控器在内的多个 `while True` 异步任务未正确注册取消逻辑。即便生命周期管理器完成了清理，`asyncio.run` 仍会因为需要等待这些失控任务而阻塞 loop 关闭。
2. **三方库死锁猜想**: 在极端情况下（如网络连接断开时 Disconnect），某些三方库底层线程可能阻塞主循环。
3. **日志盲区**: Alembic 迁移在启动阶段失败时，其 stdout/stderr 捕获在同步执行模式下偶尔失效，导致无法追溯迁移冲突。

## 3. 核心修复方案
- **任务治理**: 对 `UpdateService` 的所有子任务实施显式追踪与 Cancel 机制。
- **双重保险退出**: 在 `main.py` 引入 40s 硬超时保护，若优雅关闭超时，直接通过 `os._exit` 强制归还控制权给 `entrypoint.sh`。
- **异步诊断增强**: Alembic 现在采用异步进程执行，能够 100% 记录迁移错误细节。

## 4. 验证情况
- **单元测试**: `test_update_service_industrial.py` 与 `test_sleep_manager.py` 全部通过，证实了异步任务取消逻辑的有效性。
- **集成测试**: 编写并执行了 `test_full_update_flow.py`，模拟了从 `/update` 命令触发、生成 `UPDATE_LOCK.json`、设置退出码 10，到重启后自动执行 `post_update_bootstrap` 的全链路流程。
- **鲁棒性验证**: 模拟了数据库迁移失败场景，证实系统能正确从 `auto_update` 备份中执行原子回滚。
- **挂机防护**: 已注入 40s 强制退出门禁，彻底解决“停在 Shutdown Complete 但进程不退出”的顽疾。

---
**交付 ID**: 20260210_Fix_Update_Failure_Deep
**状态**: 修复代码已就绪，等待最终推送。
