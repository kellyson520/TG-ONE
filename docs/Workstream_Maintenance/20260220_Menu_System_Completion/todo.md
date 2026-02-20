# 补全机器人菜单界面与缺失功能

## 背景 (Context)
用户反馈 `AttributeError: 'MenuController' object has no attribute 'show_dedup_video'`，并要求补全缺失按钮、功能、归档菜单及 Bot 菜单界面的二级三级界面。当前架构已迁移至 CVM (Controller-View-Module) 模式，需要确保所有 Action 都有对应的处理链路。

## 待办清单 (Checklist)

### Phase 1: 基础骨架补全 (Skeleton)
- [x] 补全 `MenuController` 中缺失的方法 (`show_dedup_video` 及其他去重子界面)
- [x] 确保 `NewMenuSystem` 正确代理这些调用
- [x] 检查 `DedupMenuStrategy` 中的 Action 路由

### Phase 2: 功能深度补全 (Features)
- [x] 补全归档管理界面 (Archive Hub)
- [x] 补全媒体过滤的高级二级界面 (Interactive Matrix)
- [x] 补全 AI 增强的全局设置界面 (System-wide Panel)
- [x] 补全系统设置中的清理/备份二级界面 (Verified)

### Phase 3: UI 渲染对齐 (UI Alignment)
- [ ] 验证 `DedupRenderer` 包含所有必需的渲染方法
- [ ] 验证 `MediaRenderer` 包含所有必需的渲染方法
- [ ] 验证 `TaskRenderer` 包含所有必需的渲染方法

### Phase 4: 验证与清理 (Verification)
- [ ] 运行静态检查验证所有方法调用
- [ ] 生成交付报告
- [ ] 同步 `docs/tree.md`
