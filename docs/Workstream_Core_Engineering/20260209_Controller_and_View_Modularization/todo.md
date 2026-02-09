# 控制器与视图模块化重构 (CVM) 极致细节进度表

## 0. 架构协议与交互规范 (Protocols & Standards) - [遗漏补全]
- [x] **0.1** 定义 `ViewResult` 数据结构：统一 Controller 返回给 Strategy 的数据格式（如 `Union[Tuple[str, List[Button]], None]`）
- [x] **0.2** 建立“回退（Back）”导航协议：在 `BaseView` 中实现通用的 `build_back_button(target_action)` 逻辑
- [x] **0.3** 交互状态 (State) 处理规范：定义 Controller 如何在修改数据库后清理/更新 `UserContext` 状态
- [x] **0.4** 消息操作规范：统一 `edit`（编辑现有菜单）与 `respond`（发送新消息）的决策逻辑
- [x] **0.5** 异常 UI 渲染标准：定义统一的“错误看板”渲染逻辑，替代简单的弹窗 Alert

## 1. 基础架构准备 (Foundation)
- [x] **1.1** 初始化：创建 `ui/renderers/`, `controllers/domain/`, `controllers/legacy/` 目录
- [x] **1.2** 基础渲染：在 `ui/renderers/base.py` 中实现动态分页算法（支持自定义 PageSize 和 Action 前缀）
- [x] **1.3** 控制器基类：实现 `controllers/base.py`，内置 `get_rule_or_abort` 等高频校验逻辑
- [x] **1.4** 图标字典：在 `ui/constants.py` 定义状态图标组（Progress: 🔄, Success: ✅, Info: ℹ️, Warning: ⚠️）
- [x] **1.5** 依赖注入 (DI) 更新：在 `core/container.py` 中注册所有新的 Domain 控制器单例

## 2. 规则管理 (Rule Module) - 颗粒度解耦
- [x] **2.1** `RuleRenderer.list`：实现支持分页、关键词预览和状态色彩标记的规则列表 UI
- [x] **2.2** `RuleRenderer.detail`：构建分层详情页，包括基础信息区、高级功能区和操作操作区
- [x] **2.3** `RuleController.actions`：实现启用/禁用、删除确认（防止误删）及名称修改的控制器逻辑
- [x] **2.4** 关键词交互重构：迁移“输入关键词 -> 回调处理 -> 结果回显”的完整异步状态链路
- [x] **2.5** 同步配置 (Sync) 深度迁移：处理跨规则配置镜像同步时的 UI 反馈（已通过 RuleController 委托处理）

## 3. 管理与系统 (Admin Module) - 运维安全拆分
- [x] **3.1** `AdminRenderer.health`：实现数据库连接池状态、内存占用及磁盘配额的可视化面板
- [x] **3.2** `AdminController.backup`：实现备份文件的分页展示、删除过期备份及一键恢复的安全校验
- [x] **3.3** 维护模式逻辑：在 `AdminController` 实现全局维护模式切换及其对其他控制器的拦截作用
- [x] **3.4** 日志实时追踪 (Stream)：重构日志查看功能，支持按关键词过滤和实时刷新缓存
- [x] **3.5** 系统参数动态调整：从菜单中直接修改 `.env` 环境参数的预检查与即时应用逻辑

## 4. 媒体、AI 与 去重 (Media/AI/Dedup) - 智能模块整合
- [x] **4.1** `MediaRenderer`：实现媒体扩展名、媒体类型、时长/大小限制的开关矩阵（Matrix UI）
- [x] **4.2** AI 提示词工作流：重构提示词设置提示，支持当前提示词预览与“恢复默认”一键操作
- [x] **4.3** 去重扫描管理器：在 `MediaController` 实现扫描任务的长连接状态监听（防止 UI 阻塞）
- [x] **4.4** 模型选择器重构：支持按 Providers (OpenAI/Anthropic/Local) 分组显示 AI 模型列表
- [x] **4.5** 历史补全 (History) 状态控制：迁移历史任务启动、暂停及错误重试的控制器逻辑

## 5. 整合与收尾 (Integration & Legacy Burial)
- [x] **5.1** `MenuFacade` 代理实现：将所有 `menu_controller.method` 指向新的 Domain 控制器
- [ ] **5.2** 渲染层单元测试：在不启动 Bot 的情况下，验证 `View` 生成的 HTML 标签是否完整闭合
- [x] **5.3** 物理文件大迁徙：将 1400 行的旧文件移除并处理所有 `import` 引用冲突 (已大幅缩减并完成委托)
- [x] **5.4** 生命周期审计：检查各控制器在 `__init__` 阶段是否存在耗时操作（优化完成，采用 Lazy Loading）
- [ ] **5.5** UI 一致性检查：确保全系统按钮的宽度、颜色标记和图标使用规范完全统一

## 6. 高可用与体验增强 (UX & HA) - [未来扩展]
- [ ] **6.1** 菜单响应缓存 (MemCached)：为高频访问的“主菜单”和“规则列表”引入 3 秒快速缓存
- [ ] **6.2** 防抖机制 (Debounce)：在 Controller 层面防止用户快速多次点击造成的数据库写竞争
- [ ] **6.3** 智能引导 (Onboarding)：在空规则列表或新用户首次进入时渲染“快速开始”引导 UI
