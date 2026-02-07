# 三重错误修复技术方案

## 1. 去重仓库修复 (DedupRepository)
- **原因分析**: `MediaSignature` 模型初始化时被传入了 `message_id`，但该模型定义中可能不包含此字段。
- **预定修复**: 检查调用 `MediaSignature` 的地方，移除无效参数。

## 2. 回调处理器修复 (Generic Toggle)
- **原因分析**: `handle_callback` 在分派任务时传入了 `rest` 参数，但 `handle_generic_toggle` 的定义签名中未包含该参数或 `**kwargs`。
- **预定修复**: 在 `handlers/button/callback/callback_handlers.py` 中更新 `handle_generic_toggle` 签名。

## 3. 分析中心列表修复 (Menu Controller)
- **原因分析**: 在渲染或处理分析中心列表时，尝试访问字典中的 `'name'` 键但该键不存在。
- **预定修复**: 检查 `controllers/menu_controller.py`。添加防御性检查。
