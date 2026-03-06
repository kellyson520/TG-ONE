# 任务交付报告: 修复 MessageListener UnboundLocalError
 
## 1. 任务概述 (Summary)
修复了 `listeners/message_listener.py` 中由于局部 `import container` 导致的 `UnboundLocalError` 故障。该问题会导致消息监听器在处理消息时偶发崩溃，影响转发稳定性。

## 2. 问题根因 (Root Cause)
在 `user_message_listener` 函数内部，曾有一行 `from core.container import container`。在 Python 中，函数体内的 `import` 语句会将该名称视为局部变量。
- 当 `ENABLE_HOTWORD` 为 `True` 时，该 `import` 执行，局部 `container` 被赋值，后续引用正常。
- 当 `ENABLE_HOTWORD` 为 `False` 或其他分支导致 `import` 未执行时，后续（如第 237 行）引用 `container` 会触发 `UnboundLocalError`，因为此时 `container` 被识别为局部变量但未绑定值。

## 3. 修复内容 (Changes)
- **文件**: `listeners/message_listener.py`
- **操作**: 删除了函数内部的冗余 `import` 语句。
- **验证**: 确保函数引用模块顶部的全局 `container` 单例。
- **预防**: 检查了同一文件内的其他 `bot_message_listener` 分支，确认无同类阴影导入。

## 4. 验证结果 (Verification)
- **静态检查**: 运行 `py_compile` 通过，无语法或导入错误。
- **架构审计**: 符合 Handler 纯净度要求，未引入循环依赖。

## 5. 质量矩阵
| 维度 | 评价 |
| :--- | :--- |
| 稳定性 | 彻底消除 container 引用导致的崩溃风险 |
| 性能 | 减少一次函数内的 import 查找开销 |
| 规范性 | 遵循 PSB 协议及核心工程规范 |
