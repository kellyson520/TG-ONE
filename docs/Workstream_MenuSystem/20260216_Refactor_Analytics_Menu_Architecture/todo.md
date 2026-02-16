# Task: 数据分析菜单架构重构 (Analytics Menu Architecture Refactoring)

## 1. 背景 (Background)
之前的数据分析详细页面（详细统计）直接在 `handlers` 中硬编码了字符串渲染，不符合项目现有的控制器-渲染器 (CVM) 架构。
用户要求统一使用现有渲染引擎渲染。

## 2. 目标 (Objectives)
- [x] 在 `services/analytics_service.py` 中补全所需的数据项（如消息类型分布）。
- [x] 在 `MainMenuRenderer` 中增强 `render_forward_analytics` 支持类型分布展示。
- [x] 在 `AdminController` 中标准化详细统计的展示逻辑。
- [x] 在 `MenuController` 中补充缺失的分析跳转方法。
- [x] 在 `AnalyticsMenu` (Handler) 中移除硬编码渲染，改为调用 `MenuController`。

## 3. 方案设计 (Spec)
### 3.1 数据层
- `AnalyticsService.get_detailed_analytics`: 增加 `type_distribution` 返回。

### 3.2 控制层
- `MenuController` 增加 `show_detailed_analytics`, `show_performance_analysis`, `show_failure_analysis` 等方法。
- 代理至 `AdminController` 的对应实现。

### 3.3 表现层
- `MainMenuRenderer.render_forward_analytics`: 增加“内容类型分布” Section。

## 4. 进度记录 (Todo)
- [x] 扩展 AnalyticsService 数据接口
- [x] 增强 MainMenuRenderer 渲染模版
- [x] 补全 AdminController 管理逻辑
- [x] 补全 MenuController 调度接口
- [x] 重构 AnalyticsMenu 处理器实现
- [ ] 验证全流程点击跳转与渲染效果
