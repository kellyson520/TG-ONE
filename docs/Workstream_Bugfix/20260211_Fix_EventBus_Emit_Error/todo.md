# Fix EventBus Emit Error

## 背景 (Context)
在系统关闭过程中，`core.bootstrap` 尝试调用 `EventBus.emit()`，但该类仅定义了 `publish()` 方法，导致报错：`'EventBus' object has no attribute 'emit'`。

## 待办清单 (Checklist)

### Phase 1: 核心修复
- [x] 确认 `EventBus` 中的方法定义 (已确认: `publish`)
- [x] 修改 `core/bootstrap.py` 中的 `emit` 为 `publish`
- [x] 检查代码中是否有其他地方误用了 `emit` (除日志模块外，已清理)
- [x] 修复 `services/rule/crud.py` 中 `publish` 缺失 `await` 的问题

### Phase 2: 验证与清理
- [x] 运行静态检查验证
- [ ] 生成任务报告
- [ ] 更新 process.md
