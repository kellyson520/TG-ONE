# 技术方案: Worker 内存保护与通知治理

## 1. 背景分析
当前内存保护逻辑存在逻辑冲突：
- `mem_warning = 250MB`
- `mem_critical = 150MB`
导致内存一旦超过 150MB 就会直接触发 Critical 逻辑（熔断并发送 ERROR 告警）。

## 2. 方案调整

### 2.1 配置属性修正
在 `core/config/__init__.py` 中：
- 修改 `MEMORY_WARNING_THRESHOLD_MB` 默认值为 `512`。
- 修改 `MEMORY_CRITICAL_THRESHOLD_MB` 默认值为 `800`。
- 确保 `MEMORY_WARNING_THRESHOLD_MB < MEMORY_CRITICAL_THRESHOLD_MB`。

### 2.2 熔断逻辑平滑化
在 `services/worker_service.py` 的 `_monitor_scaling` 中：
1. **状态锁定**: 触发 Critical 熔断后，设置一个冷却时间（例如 5 分钟），在此期间不再重复发送 ERROR 告警。
2. **渐进式 GC**:
   - Warning 阶段：`gc.collect(1)` (分代回收)
   - Critical 阶段：`gc.collect()` + `time.sleep(1)` + `gc.collect()` (确保回收彻底)
3. **日志降噪**: 连续触发同一级别的资源警告时，仅在第一次发送推送告警。

## 3. 实施细节
- 检查 `psutil` 获取的 RSS 含义，确保监控指标与操作系统一致。
- 在 `.env` 中增加说明，指导低配置 VPS 用户如何设置这些值。
