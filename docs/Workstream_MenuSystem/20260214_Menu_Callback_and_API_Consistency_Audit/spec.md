# 技术方案: 菜单系统一致性治理 (Technical Spec: Menu System Consistency Governance)

## 1. 目标 (Objectives)
- 消除机器人菜单中的“未开发”占位符。
- 确保 Web 管理端与 Bot 端的 API 调用路径、参数完全一致。
- 保证系统状态（Settings, Rules）在两端实时/近实时同步。

## 2. 核心组件分析 (Core Analysis)

### 2.1 UI 构建引擎 (Upgrade to UIRE-3.0)
为了从底层根本性解决“点击无响应”和“链路中断”问题，UI 生成器已升级至 **UIRE-3.0**，核心改进如下：
- **Callback Guard (64B)**: 自动校验 Telegram 回调数据长度，防止因参数过长导致的静默失败。
- **Auto-Prefixer**: 核心方法 `add_button` 现在会自动为 action 补全 `new_menu:` 前缀，除非显式禁用。这解决了开发者忘记添加前缀导致的路由丢失。
- **Smart Layout & Breadcrumb**: 引入 🗺️ 增强型地图样式面包屑和针对长标签的自动栅格换行。
- **Alert Components**: 新增 `add_alert` 方法，用于在菜单中插入醒目的警告块，统一错误展示。

### 2.2 虚假数据源 (Fake Data Tracing)
- **AnalyticsService**: 硬编码了 `current_tps` (12.5) 和 `avg_response_time` (0.5)，以及 70/30 的消息类型分布，导致 UI 展示的是非真实运行数据。

### 2.3 Web 管理端
- **Frontend/Backend**: 通过 `api-contract-manager` 验证请求与路由的 1:1 映射关系，防止 Web 端操作失效。

## 3. 审计方案 (Audit Plan)

### 3.1 占位符搜索
使用 `grep` 搜索：
- `未开发`
- `功能缺失`
- `developing`
- `coming soon`
- `pass` (空函数体)

### 3.2 接口一致性工具
调用 `api-contract-manager/scripts/audit_api.py` 自动扫描 `web_admin` 中的 `fetch/axios` 调用并与 FastAPI 的 `@router` 装饰器进行比对。

### 3.3 回调校验逻辑
1. 提取所有 `ui/*.py` 中硬编码的 `callback_data` 字符串。
2. 搜索 `handlers/*.py` 中所有 `@bot.on(events.CallbackQuery)` 的匹配模式。
3. 标注无 Handler 对应的 Callback。

## 4. 数据同步协议
- 所有的状态变更必须通过 `ServiceProvider` 进行。
- 引入 `EventBus` (如果已存在) 或 `Cache Invalidation` 机制，确保一端修改后，另一端在下次读取时能获取最新数据。
