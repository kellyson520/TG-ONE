# Report: Fix Async SystemExit Error

## 1. 任务背景 (Background)
用户报告在触发系统更新时出现 `RuntimeError: Event loop is closed`。这是由于在异步回调中直接调用 `sys.exit()` 导致事件循环被强行终止，而底层网络传输仍在尝试运行，从而引发崩溃日志。

## 2. 核心改动 (Core Changes)
### 2.1 生命周期管理增强 (`core/lifecycle.py`)
- 引入了 `asyncio.Event` 类型的 `stop_event`。
- 实现了 `shutdown(exit_code)` 方法，用于发出关闭信号而不立即终止进程。

### 2.2 主循环架构优化 (`main.py`)
- 将 `main()` 调整为等待 `lifecycle.stop_event`。
- 在退出前显式调用 `lifecycle.stop()` 确保所有服务（Telegram 客户端、数据库缓冲、布隆过滤器）完成优雅清理。
- 由同步入口点根据 `lifecycle.exit_code` 执行物理退出。

### 2.3 业务逻辑适配 (`services/update_service.py`)
- 将所有 `sys.exit(EXIT_CODE_UPDATE)` 替换为 `container.lifecycle.shutdown(EXIT_CODE_UPDATE)`。
- 通过 `container` 代理访问生命周期管理器，避免循环依赖。

## 3. 验证矩阵 (Quality Matrix)
- [x] **架构合规性**: 遵循 CVM 模式，将关闭逻辑归口至生命周期管理器。
- [x] **性能影响**: 无明显开销，消除了退出时的 TCP 传输报错日志。
- [x] **稳定性**: 通过 `tests/verification/test_async_shutdown.py` 模拟测试，验证了退出码传递与资源清理的完整性。

## 4. 结论 (Conclusion)
系统现在支持在异步任务中安全触发重启/退出，消除了“Event loop is closed”系列异常，提升了系统更新过程中的日志整洁度与资源安全性。
