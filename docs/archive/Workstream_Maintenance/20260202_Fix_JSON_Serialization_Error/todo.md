# 修复 JSON 序列化失败 (Fix JSON Serialization Error)

## 背景 (Context)
系统抛出 `TypeError: Object of type function is not JSON serializable` 错误。
具体发生在 `repositories/task_repo.py` 的 `push` 方法和 `handlers/commands/rule_commands.py`。
这通常是因为在尝试将包含函数对象的字典序列化为 JSON 时触发的。

## 待办清单 (Checklist)

### Phase 1: 诊断与分析
- [x] 定位 `repositories/task_repo.py` 中的错误点
- [x] 定位 `handlers/commands/rule_commands.py` 中的错误点
- [x] 确定 `payload` 或 `task_data` 中哪个字段包含了函数对象

### Phase 2: 修复实现
- [x] 在序列化前过滤或转换函数对象
- [x] 确保 `push` 任务时的 payload 是纯数据结构
- [x] 修复 `rule_commands` 中的删除消息逻辑

### Phase 3: 验证
- [x] 运行相关的命令触发修复后的逻辑
- [x] 检查日志确保不再出现序列化错误
- [x] 执行 `local-ci` 确保没有回归问题
