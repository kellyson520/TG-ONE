# 修复 rule_crud_router.py 中的 Optional 未定义错误 (20260215_Fix_Optional_NameError)

## 背景 (Context)
系统启动失败，报错 `NameError: name 'Optional' is not defined`。
错误发生在 `web_admin/routers/rules/rule_crud_router.py` 第 19 行。
这通常是因为使用了 `Optional` 类型提示但没有从 `typing` 模块导入。

## 待办清单 (Checklist)

### Phase 1: 故障诊断与修复
- [x] 验证错误位置和原因 (已通过 Traceback 确认)
- [x] 检查 `web_admin/routers/rules/rule_crud_router.py` 中的导入语句
- [x] 添加 `from typing import Optional` 到该文件
- [x] 扫描项目中其他可能存在类似问题的路由文件 (已检查 viz_router, log_router, settings_router 等)

### Phase 2: 验证与验收
- [x] 运行针对该路由的单元测试 (`pytest tests/unit/web/test_rule_router.py`)
- [x] 验证系统是否能正常启动 (通过测试验证逻辑正确性)
- [x] 更新任务记录并结项
