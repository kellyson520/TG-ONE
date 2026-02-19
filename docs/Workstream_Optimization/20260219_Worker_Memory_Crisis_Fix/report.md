# 任务报告: Worker 内存熔断倒置与告警降噪修复

## 摘要 (Summary)
成功修复了 `WorkerService` 在资源监控中的逻辑倒置问题，并大幅调高了内存阈值预设，解决了因配置过于保守导致的虚假告警与分发器频繁中断问题。同步实现了告警降噪逻辑，确保系统在持续压力下不会通过 Telegram 轰炸管理员。

## 架构变更 (Architecture Refactor)
- **配置层**: 修正 `core/config/__init__.py` 中的 `MEMORY_WARNING_THRESHOLD_MB` 和 `MEMORY_CRITICAL_THRESHOLD_MB`。默认值从 250/150 调整为 512/1024。
- **服务层 (WorkerService)**: 
    - 引入 `critical_mode` 状态机，防止熔断期间重复尝试启动分发。
    - 实现告警冷却（5分钟），将重复的 ERROR 告警降级为 WARNING。
    - 强化 GC 策略，Critical 模式下执行更深层的 `gc.collect(2)`。
- **服务层 (GuardService)**: 同步全局内存限制设置。

## 验证结果 (Verification)
- 验证脚本确认配置加载正确，逻辑顺序已恢复正常（Critical > Warning）。
- 内存限制已提升至 1024MB，能有效容纳典型运行负荷（~400MB RSS）。
- 已在 `WorkerService` 中验证状态机的一致性。

## 用户操作建议 (Manual)
如果服务器内存极低（小于 1GB），建议在 `.env` 中手动设置：
```env
MEMORY_WARNING_THRESHOLD_MB=300
MEMORY_CRITICAL_THRESHOLD_MB=450
```
正常情况下，默认的 512MB/1024MB 适用于大多数 VPS 环境。
