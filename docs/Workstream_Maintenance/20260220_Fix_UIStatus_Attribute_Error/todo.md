# 修复 UIStatus.DELETE 属性缺失错误

## 背景 (Context)
在会话管理功能中，`SessionRenderer` 尝试访问 `UIStatus.DELETE` 属性，但 `ui/constants.py` 中该常量名为 `TRASH`。这导致了 `AttributeError` 并使得整个会话管理页面无法加载。

## 待办清单 (Checklist)

### Phase 1: 启动 (Initialization)
- [x] 分析错误堆栈并定位代码
- [x] 阅读并激活相关技能 (task-lifecycle-manager, core-engineering)
- [x] 初始化任务文档 (todo.md, spec.md)

### Phase 2: 设置 (Setup)
- [x] 备份相关文件 (ui/constants.py)

### Phase 3: 构建 (Build)
- [x] 在 `ui/constants.py` 中为 `UIStatus` 类添加 `DELETE` 属性
- [x] 检查并验证 `session_renderer.py` 的用法

### Phase 4: 验证 (Verify)
- [x] 运行静态检查确保无语法错误
- [x] (可选) 运行相关单元测试（如果存在）
- [x] 验证 `docs/tree.md` 同步状态

### Phase 5: 报告 (Report)
- [x] 编写 `report.md`
- [x] 更新 `docs/process.md` 状态为 100%
- [x] 清理临时文件
