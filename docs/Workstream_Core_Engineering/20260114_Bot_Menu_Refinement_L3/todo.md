# 任务清单: 机器人菜单系统三级联动与精细化迁移 (20260114)

## 状态说明
- 领域: 核心工程 (Workstream_Core_Engineering)
- 优先级: 高
- 进度: 80% (核心迁移完成)

## 第一阶段: 规划与设计 (Plan) ✅
- [x] 历史查重与代码审计 (从源项目 `TelegramForwarder-1.7.6-2` 提取逻辑)
- [x] 定义三级菜单结构规范 (Level 1: 主页 -> Level 2: 分中心 -> Level 3: 功能管理)
- [x] 编写技术规范文档 (`spec.md`)

## 第二阶段: 架构搭建 (Setup) ✅
- [x] 同步 `docs/tree.md` 架构树
- [x] 在 `TG ONE` 中建立 `controllers/menu_controller.py`
- [x] 在 `TG ONE` 中建立 `ui/menu_renderer.py`

## 第三阶段: 核心构建 (Build) ✅
- [x] 迁移转发管理中心 (Forward Hub - Level 2)
- [x] 迁移规则管理列表 (Rule List - Level 3, 分页)
- [x] 精细化规则设置界面 (Rule Detail - Level 3)
    - [x] 建立三级子菜单：基础、显示、高级
    - [x] 实现通用布尔切换逻辑 (Service + Controller)
- [x] 路由分发 (new_menu_callback.py)
- [x] 解决 `selectinload` 数据懒加载一致性问题

## 第四阶段: 验证与测试 (Verify) ⏳
- [ ] 单元测试: 菜单导航路径验证
- [ ] 集成测试: 机器人模拟点击与回调响应
- [ ] 缓存一致性验证: 修改规则后立即生效逻辑检查

## 第五阶段: 报告与收尾 (Report) ⏳
- [ ] 生成 `report.md`
- [x] 更新 `docs/process.md`
- [ ] 清理临时文件
