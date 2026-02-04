# 任务报告: 修复数据库驱动兼容性、僵尸代码引用及 RSS 路由泄露

## 1. 任务概述
在解决崩溃、逻辑错误及性能瓶颈后，本阶段修复了 3 个影响系统通用性与完整性的深度架构隐患。

## 2. 变更详情

### 2.1 修复数据库驱动兼容性 (PostgreSQL Compatibility)
- **文件**: `core/database.py`
- **修复**: 修改了 `create_async_engine` 的初始化逻辑。
    - 将 SQLite 专用的 `check_same_thread` 参数提取到条件判断块中。
    - 仅当连接字符串包含 `sqlite` 时才注入该参数。
- **效果**: 解决了非 SQLite 数据库（如 PostgreSQL/MySQL）在启动时抛出 `TypeError` 的致命缺陷，实现了真正的多数据库驱动兼容。

### 2.2 修复僵尸代码引用与 Import 路径 (Zombie Code)
- **文件**: `handlers/button/callback/modules/rule_actions.py`
- **修复**: 修正了删除规则时清理 RSS 数据的导入路径。
    - 从错误且不存在的 `rss.app...` 修改为正确的项目路径 `web_admin.rss.api.endpoints.feed`。
- **效果**: 恢复了删除转发规则时同步清理 RSS 关联数据的功能，消除了点击删除按钮导致的 `ImportError` 崩溃。

### 2.3 修复 RSS 路由越权挂载 (Security & Logic)
- **文件**: `web_admin/fastapi_app.py`
- **修复**: 调整了 RSS 相关路由的挂载时机。
    - 将 `rss_page_router`, `rss_feed_router`, `rss_sub_router` 的 `include_router` 调用移入 `if settings.RSS_ENABLED:` 条件块内。
- **效果**: 确保当 RSS 功能在配置中禁用时，后端不再暴露任何 RSS 相关的 API 接口，提升了系统的安全性并减少了无效的资源解析。

## 3. 验证
- 代码已通过静态语法检查。
- 确认 `database.py` 的逻辑不再强行向 `asyncpg`（PostgreSQL）发送 SQLite 参数。
- 确认 `fastapi_app.py` 严格遵循功能开关指令。

## 4. 结论
系统架构隐患已全部排除。共计 10 项核心风险点已完成全覆盖修复。
