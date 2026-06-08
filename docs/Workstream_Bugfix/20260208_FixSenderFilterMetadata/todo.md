# Fix SenderFilter MessageContext Metadata Attribute Error

## 背景 (Context)
在验证目标聊天实体时，`SenderFilter` 报错：`'MessageContext' object has no attribute 'metadata'`。这导致规则验证失败，可能影响消息过滤逻辑。

## 待办清单 (Checklist)

### Phase 1: 问题诊断与修复
- [x] 复现并定位代码中访问 `metadata` 的位置
- [x] 检查 `MessageContext` 的定义及初始化过程
- [x] 修复属性缺失问题（在 `MessageContext` 中添加 `metadata` 或在 `SenderFilter` 中增加容错）

### Phase 2: 验证与清理
- [x] 编写针对 `SenderFilter` 属性访问的测试用例
- [x] 确保 `local-ci` 检查通过
- [x] 提交任务报告并同步状态
