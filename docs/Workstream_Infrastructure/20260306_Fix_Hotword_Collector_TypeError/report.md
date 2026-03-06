# Task Report: Fix Hotword Collector TypeError

## Summary (概览)
修复了 `core/container.py` 中由于错误调用 `get_hotword_collector(self)` 导致的启动崩溃问题。

## Architecture Refactor (架构变更)
无架构变更。仅修正了 `Container` 初始化与启动逻辑中对单例工厂函数的调用参数。

## Implementation (实现)
- 修改 `core/container.py:line 315`: `collector = get_hotword_collector()`
- 修改 `core/container.py:line 377`: `get_hotword_collector().start_worker()`

## Verification (验证)
经审计 `middlewares/hotword.py` 中 `get_hotword_collector` 的定义：
```python
def get_hotword_collector() -> HotwordCollectorMiddleware:
    # ... 不接收任何参数
```
确认移除 `self` 参数能彻底解决该 `TypeError`。

## Manual (关键配置)
无额外配置。
