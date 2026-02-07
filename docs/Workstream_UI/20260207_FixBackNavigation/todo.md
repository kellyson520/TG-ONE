# 修复菜单返回导航错误 (Fix Menu Back Navigation Error)

## 背景 (Context)
用户反馈在部分菜单中点击返回时，会直接跳转到主菜单（"请选择要执行的操作"）而不是用户预期进入该菜单之前的页面。

## 待办清单 (Checklist)

### Phase 1: 问题定位
- [x] 确定主菜单文本所在的定义位置 (`controllers/menu_controller.py`)
- [ ] 定位所有受影响的子菜单及对应的返回按钮处理函数
- [ ] 分析受影响子菜单的 `callback_data` 结构

### Phase 2: 修复方案
- [x] 优化 `callback_handler` 的返回逻辑，确保存储或正确推断上级页面
- [x] 修正硬编码的返回路径（如果是硬编码导致的）

### Phase 3: 验证与报告
- [x] 代码静态审计，确保所有相似逻辑都已修复
- [ ] 更新 `report.md` 记录变更
- [ ] 清理临时文件，任务归档
