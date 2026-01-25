# 技术规范: 机器人菜单三级联动精细化迁移

## 1. 背景与目标
当前 `TG ONE` 机器人的菜单逻辑较为集中，导致部分设置项层级过深或展示混乱。用户要求从源项目 `TelegramForwarder-1.7.6-2` 迁移更为成熟的 Controller-Renderer 三明治架构，实现三级菜单联动，并对"转发管理"模块进行精细化拆解。

## 2. 菜单层级定义 (Hierarchy)

### Level 1: 主菜单 (Main Menu)
- [🔄 转发管理] -> Level 2: Forward Hub
- [🧹 智能去重] -> Level 2: Dedup Hub
- [📊 数据分析] -> Level 2: Analytics Hub
- [⚙️ 系统设置] -> Level 2: System Hub

### Level 2: 转发管理中心 (Forward Hub)
- [📋 规则管理] -> Level 3: Rule List
- [🕒 历史消息] -> Level 3: History Processing
- [🔍 转发搜索] -> Level 3: Search
- [⚙️ 全局设置] -> Level 3: Global Filter Settings
- [👈 返回主菜单]

### Level 3: 规则管理 (Rule List & Detail)
- **Rule List**: 分页展示规则，点击规则进入 Detail。
- **Rule Detail**:
    - [开关/基本设置] (合并)
    - [📝 关键字管理] -> Level 4: Keywords List
    - [🔄 替换规则] -> Level 4: Replace Rules List
    - [🎬 媒体设置] -> Level 4: Media Detailed Settings
    - [🤖 AI 设置] -> Level 4: AI Detailed Settings
    - [❌ 删除规则]

## 3. 技术方案 (Technical Approach)

### A. 架构模式: Controller-Renderer
- **Controller**: `controllers/bot_menu_controller.py`
    - 职责: 处理业务逻辑、调用 Service 层获取数据、准备渲染 payload。
- **Renderer**: `ui/bot_menu_renderer.py`
    - 职责: 仅负责将 payload 转换为 Telegram 合规的 `text` 和 `buttons`。
- **Entry**: `handlers/button/callback/new_menu_callback.py`
    - 职责: 路由分发。

### B. 数据流与并发优化
- **强制 Eager Loading**: 在 Controller 层使用 `selectinload` 明确加载所有 UI 依赖的关联字段 (`source_chat`, `target_chat` 等)。
- **缓存策略**: 在修改规则后，强制调用已有的 `rule_repo.clear_cache()` 以同步转发进程。

### C. UI/UX 规范
- 统一面包屑导航: `🏠 主页 > 🔄 转发管理 > ⚙️ 规则管理`
- 状态标识: 🟢 (启用) / 🔴 (禁用)
- 页码标识: `(1/5)` 位于标题或底部栏。

## 4. 迁移重点风险
1. `rule_id` 的传递链路是否闭环。
2. 现有项目中 `Service` 层接口与源项目可能存在差异，需在 Controller 层进行适配。
3. `telethon` Button 类型一致性检查。
