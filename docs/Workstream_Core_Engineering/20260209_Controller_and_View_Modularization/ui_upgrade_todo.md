# UI 渲染引擎升级 (UIRE-2.0) 极致细节实施代办

## 🎯 核心目标
建立一个“声明式”构建系统，彻底消除硬编码文本，实现 UI 与逻辑的解耦，确保系统视觉风格 100% 统一。

---

## Phase 1: 核心引擎开发 (Infrastructure) - [已完成]
- [x] **1.1** 创建 `ui/builder.py` 核心框架，定义 `MenuBuilder` 类。
- [x] **1.2** 实现 `set_title` 方法：支持图标注入、自动添加装饰符及 `━━━━━━━━━━━━━━` 动态宽度分割线。
- [x] **1.3** 实现 `add_breadcrumb` 方法：支持 `["首页", "二级"]` 格式自动渲染路径，统一分隔符。
- [x] **1.4** 开发内容块组件 `add_section`：支持可选的 Header 装饰图标，并处理 body 列表的自动换行对齐。
- [x] **1.5** 开发 `add_status_grid` 矩阵组件：实现 Key-Value 的结构化渲染，自动处理图标对齐。
- [x] **1.6** 开发 `add_progress_bar` 进度条：使用字符级渲染（Emoji + 阴影）表示百分比。
- [x] **1.7** 实现 `SmartButtonLayout`：根据按钮 Label 长度自动计算物理列数（1-3列自动适配）。
- [x] **1.8** 定义 `BaseComponent` 抽象类：为未来扩展自定义复杂组件（如：统计图表）预留接口。

## Phase 2: 基础层集成 (Base Integration) - [已完成]
- [x] **2.1** 改造 `BaseRenderer`：注入 `new_builder()` 工厂方法，确保单例或上下文隔离。
- [x] **2.2** 升级 `ViewResult` 数据结构：支持 builder 特有的元数据，如 `auto_edit_logic` 开关。
- [x] **2.3** 迁移通用异常视图：利用新引擎重构 `BaseRenderer.render_error`，支持详情折叠显示。
- [x] **2.4** 实现分页辅助器 `add_pagination`：在 Builder 中集成上一页/下一页/页码显示的原子逻辑。
- [x] **2.5** 引入 `RenderMiddleware` 机制：在输出前自动全局过滤敏感词或处理字符编码兼容性。
- [x] **2.6** 编写 `MenuBuilder` 单元测试桩：验证生成的字符串在不同屏幕宽度下的对齐表现。

## Phase 3: 试点迁移 (Pilot Migration: Admin) - [已完成]
- [x] **3.1** 迁移 `AdminRenderer.render_system_hub`：应用面包屑导航和分层 Section 布局。
- [x] **3.2** 迁移 `AdminRenderer.render_db_performance_monitor`：使用 `status_grid` 动态展示 CPU/内存指标。
- [x] **3.3** 迁移 `AdminRenderer.render_db_optimization_center`：使用进度条显示当前数据库分析完整度。
- [x] **3.4** 迁移 `AdminRenderer.render_db_backup`：重构备份列表分页 UI，统一删除按钮的 DANGER 图标。
- [x] **3.5** 迁移 `AdminRenderer.render_cache_cleanup`：实现分行统计数据与一键清理按钮的视觉隔离。
- [x] **3.6** 迁移运行日志预览：利用 Builder 开发日志流预览组件，支持按等级（Level）自动上色（表情符号）。

## Phase 4: 全量领域迁移 (Universal Migration) - [已完成]
- [x] **4.1** `MediaRenderer` 全量迁移：涵盖历史任务中心、任务详情及 AI 总结设置页面。
- [x] **4.2** `RuleRenderer` 复杂列表重构：实现带关键词预览缩略图的规则列表 UI。
- [x] **4.3** `RuleRenderer` 详情页重写：使用 Section 聚合基础设置、媒体配置与高级同步策略。
- [x] **4.4** `SettingsRenderer` 矩阵迁移：重构 10+ 种布尔开关设置项的统一渲染模板。
- [x] **4.5** `AI Prompt` 设置工作流重构：实现“当前提示词展示”与“输入框提示”的组合视图。
- [x] **4.6** 实现全局“操作确认”渲染器：为所有删除、重启、重置等危险操作提供统一样式的二次确认页。

## Phase 5: 清理与标准审计 (Final Cleanup) - [已完成]
- [x] **5.1** 执行 `ui/constants.py` 瘦身：移除所有已经硬编码到 Builder 内部的模板字符串常量。
- [x] **5.2** 批量物理删除 Renderer 文件中的 f-string 逻辑，确保 Renderer 代码仅保留数据映射逻辑。
- [x] **5.3** 统一图标命名规范大审计：确保全系统使用的表情符号在 `UIStatus` 中唯一引用。
- [x] **5.4** 执行“极端压力测试”：测试在超长规则名、超多按钮场景下的 Builder 自动截断与换行表现。
- [x] **5.5** 编写《UI 开发参考手册》：提供 Builder 的典型代码片段（Snippets）供新功能参考。
- [x] **5.6** 最终视觉一致性核对：确认 breadcrumb 在全系统的路径深度与风格完全同步。

---

## 🛠️ 全面审查记录 (Master Audit: V2-Detailed)

| 检查项 | 状态 | 结论 |
| :--- | :--- | :--- |
| **颗粒度覆盖** | 🟢 | 任务已细化到原子级，每阶段至少 6 个任务，确保执行无死角。 |
| **逻辑递归检查** | 🟢 | 确认 Phase 2 的分页器与 Phase 4 的列表重构之间存在明确的调用依赖。 |
| **视觉一致性** | 🟢 | 分割线宽度、面包屑分隔符、DANGER 按钮图标已全部内置。 |
| **性能效率** | 🟢 | 采用“一次构建模式(Lazy Build)”，对比直接拼接，性能开销依然控制在微秒级。 |

---
**实施备注：** 每个子任务完成后，须在 `todo.md` 中手动标记。
