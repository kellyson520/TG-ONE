# 修复回调与导入错误 (Fix Callback and Import Errors)

## 背景 (Context)
近期重构(可能是日期选择器升级或菜单审计)引入了三处回归错误:
1. `history.py` 错误的导入了不存在的顶级 `utils` 模块。
2. `callback_handlers.py` 中引用了未定义的 `container` 变量。
3. `KeywordFilter` 的智能去重逻辑可能存在干扰或逻辑报错(需进一步确认日志含义)。

## 待办清单 (Checklist)

### Phase 1: 错误诊断与修复
- [x] 修复 `handlers/button/modules/history.py` 中的 `ModuleNotFoundError: No module named 'utils'`
  - 已将 `from utils.telegram_utils import safe_edit` 修正为 `from services.network.telegram_utils import safe_edit`
- [x] 修复 `handlers/button/callback/callback_handlers.py` 中的 `NameError: name 'container' is not defined`
  - 已添加 `from core.container import container` 导入
- [x] 调查 `filters/keyword_filter.py` 的处理中断逻辑,确保其行为符合预期
  - 已添加历史任务跳过智能去重的逻辑,避免中断处理链
  - 已添加目标聊天安全检查,防止 AttributeError
  - 已在 Pipeline 中传递 `is_history` 标记

### Phase 2: 验证与验收
- [ ] 编写/运行针对性测试,确保修复有效且无副作用
- [ ] 检查并清理根目录临时文件
- [ ] 提交任务报告 (`report.md`)
