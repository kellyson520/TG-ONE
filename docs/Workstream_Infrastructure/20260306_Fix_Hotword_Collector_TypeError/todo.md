# 修复 Hotword Collector 调用参数错误 (TypeError)

## 背景 (Context)
系统在启动时抛出 `TypeError: get_hotword_collector() takes 0 positional arguments but 1 was given`，导致 Container 初始化失败。这是因为在 `core/container.py` 中错误地将 `self` (Container 实例) 传递给了 `get_hotword_collector()`，而该函数在定义中不接受任何参数。

## 策略 (Strategy)
1.  修改 `core/container.py`，移除 `get_hotword_collector()` 调用中的 `self` 参数。
2.  同步更新 `container.py` 中启动 Hotword 任务的调用。
3.  验证修复后系统是否能成功引导。

## 待办清单 (Checklist)

### Phase 1: 核心修复
- [x] 修改 `core/container.py` 中的 `init_with_client` 方法，移除调用 `get_hotword_collector` 时传递的 `self` 参数。
- [x] 修改 `core/container.py` 中的 `start_all` 方法，同步更新。

### Phase 2: 验证
- [x] 核心修复已完成并审计。
- [x] 确认 get_hotword_collector() 参数定义。

## 报告 (Report)
- [x] 编写 `report.md` 并归档。
