# 修复 MessageListener UnboundLocalError: container
 
## 背景 (Context)
在 `listeners/message_listener.py` 中，消息处理偶发失败，抛举 `UnboundLocalError: cannot access local variable 'container' where it is not associated with a value`。这是因为在 `user_message_listener` 函数内部存在一个局部 import Shadow 了全局 `container` 变量，而在某些路径下（如热词开关关闭时）该局部 import 未被执行，导致后续引用失效。

## 策略 (Strategy)
1. 移除 `user_message_listener` 内部 redundant 的 `from core.container import container`。
2. 确保统一使用模块顶部的全局 `container`。
3. 验证其他类似潜在问题。

## 待办清单 (Checklist)

### Phase 1: 故障修复
- [x] 移除 `listeners/message_listener.py:156` 的冗余 import
- [x] 检查 `user_message_listener` 中所有 `container` 引用是否已对齐到全局变量
- [x] 修复 `listeners/message_listener.py` 中其他可能的同类隐患

### Phase 2: 验证与验收
- [x] 代码风格检查
- [ ] (可选) 模拟消息监听测试（如果环境允许）
- [ ] 生成交付报告并归档
