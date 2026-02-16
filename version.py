VERSION = "1.2.6.3"

UPDATE_INFO = """
**更新日志**
- v1.2.6.3: 修复菜单系统交互缺陷
  - 修正 MenuController.toggle_rule_status 参数传递错误
  - 解决规则切换时的 TypeError
- v1.2.7.0: MenuController 及领域控制器架构标准化重构 (UIRE-3.0)
  - 核心重构：实现 MenuController 与领域控制器 (Media/Rule/Admin) 的彻底解耦
  - UI 标准化：引入 `display_view` 统一渲染入口，消除控制器内所有硬编码 UI 字符串
  - 渲染内聚：将标题、面包屑、分割线等结构完全收敛至 Renderer 层 (MenuBuilder 驱动)
  - 修复逻辑：解决 Telegram 消息双重标题/面包屑冗余问题，修复 Emoji 编码混乱
  - 路线对齐：全系菜单路由现在强制通过 Controller 分发，确保全链路遵循 CVM 模式
- v1.2.6.0: Web 管理端服务端搜索与分页功能升级
  - 核心仓库增强：实现 RuleRepository 与 StatsRepository 的服务端关键词搜索逻辑
  - 接口标准化：为 Rules 与 Logs API 引入分页参数 (Page/Size) 与搜索参数 (Query)
  - 前端 UI 优化：
    - Rules 页面支持实时防抖搜索与服务端分页跳转
    - History 页面集成 URL 级联过滤 (支持通过规则 ID 直接定位)
    - 修复 History 详情页展示逻辑与 TypeScript 类型报错
- v1.2.5.5: 系统更新/重部署交互体验修复
  - 修复确认页面“取消”按钮报错（Action: `data="delete"` -> `data="cancel"`）
  - 完善回调路由器对 `cancel` 指令的免 ID 校验与通用分发逻辑
- v1.2.5.4: 系统稳定性与代码质量专项优化
  - 修复 AnalyticsService._resolve_chat_name 中未命名的 session_service 引用
  - 修复 AdminController 中清理日志逻辑的未定义变量与缺失导入
  - 修复回调处理器 mapping 中 delete_duplicates 的 undefined name 错误
- v1.2.5.3: Web 管理界面稳定性与鲁棒性修复
- v1.2.5.1: 更新自愈与健康检查稳定性优化
  - 修复 UpdateService 健康检查重复计数导致的回滚死循环
  - 引入 UpdateService 的进程级单次验证锁 (Health Check Debounce)
  - 在系统更新观察期内自动抑制 GuardService 的文件变更热重启
- v1.2.5.0: UIRE-2.0 渲染引擎与 CVM 架构模块化
  - 核心渲染引擎升级：支持原子行控制、智能流式布局及吸底按钮自动排列
  - 引入 UI 鲁棒性守卫：3800 字符硬截断、智能 ID 缩略及 Markdown 逃逸保护
  - 完成 CVM 架构重构：将 UI 逻辑从处理器彻底解耦至领域控制器与专属渲染器
  - 统一视觉语言：全系统的面包屑导航标准化、30+ 状态图标规范化
- v1.2.4.5: QoS 4.0 动态泳道路由 (Lane Routing) 完整版
  - 实现物理隔离的 Critical/Fast/Standard 三泳道系统
  - 引入 汉化版 拥塞感知路由 (CAP) 与 动态评分日志显示
  - 修复 /vip 指令在 QoS 4.0 下的描述对齐问题
- v1.2.4.4: 构建系统升级与核心 Bug 修复 - 迁移至 `uv` 包管理器以提升 5x 构建效率；修复 `SenderFilter` 中 `MessageContext` 缺失 `metadata` 属性导致的转发中断；实现多级优先级队列解决高负载延迟；修复启动阶段 Bot 命令导入错误与关闭流程冗余。
- v1.2.4.3: 工业级更新交互与故障自愈 - 引入 Uptime Guard (故障自动回滚)、UPDATE_VERIFYING 稳定性观察机制及物理包 Failover；新增 `manage_update.py` CLI 工具与 Bot 端带二次确认的 `/update`、`/rollback` 指令。
- v1.2.4.2: 修复 Bot 命令菜单乱码 - 深度分析并修复了 `bot_commands_list.py` 中的双重编码破坏，恢复了所有中文字符描述与 Emoji，并通过语法校验与单体修复确保了命令注册的稳定性。
- v1.2.4.1: 运维卫生与关闭流程优化 - 增强 `entrypoint.sh` 依赖检查日志可见性，修复重复关闭导致的警告噪音，移除启动异常块中的冗余停止调用，并完成历史任务的自动化归档清理。
- v1.2.4.0: 去重引擎健壮性及逻辑冲突修复 - 修复 DedupRepository AttributeError (batch_add 命名不一致), 解决 KeywordFilter 与 DedupMiddleware 双重校验导致的误判拦截, 完善缓冲区回滚机制与相似度引擎变量初始化。
- v1.2.3.9: 数据库监控与高级去重 - 新增数据库性能监控面板 (Query Analysis/Trends/Alerts), 集成规则级去重高级配置 (自定义相似度/时间窗口), 优化 `db_maintenance_service` 交互体验。
- v1.2.3.8: 去重引擎 V3 升级 - 引入 Numba 加速、LSH Forest 语义类似检索、SSH v5 视频采样哈希、Tombstone 状态管理及策略模式重构,大幅提升性能与检索精度。
- v1.2.3.7: 统计与文档增强 - 新增“拦截流量”统计 (SmartDeadup/Main Menu)、完善 FAQ 与详细文档功能、修正菜单回调交互。
- v1.2.3.6: 回调与导入错误修复 - 修复 history.py 模块导入路径错误 (utils→services.network)、callback_handlers.py 缺失 container 导入、KeywordFilter 历史任务去重逻辑优化,确保历史消息转发流程正常运行。
- v1.2.3.5: 启动稳定性修复 - 解决 `core.container` 与中间件/服务层之间的循环导入问题,确保系统在生产环境下正常启动。
- v1.2.3.4: 代码卫生与回归修复 - 修复 Admin Callback 中的未定义名称 (select/ForwardRule),统一数据库 Session 调用范式,重构版本信息显示逻辑 (Version Pagination)。
- v1.2.3.3: 交互与更新逻辑修复 - 修正更新检查逻辑中的 SHA 比对及 API URL 错误;修复转发规则绑定后的路由丢失 (rule_settings:New) 问题;推进菜单系统 (NewMenuSystem) 审计与功能补全,修复多处回调参数不匹配引发的崩溃。
- v1.2.3.2-A: 工程清理 - 移除云端 CI (GitHub Actions) 依赖,完全转向本地 CI 驱动;修复日志与任务重复问题;增强菜单系统稳健性 (Callback/AttributeError Fixes)。
- v1.2.3.2: 运维稳定性增强 - 修复日志系统中的二次噪音 (Auth/DB),优化数据库维护扫描逻辑 (排除备份),修复 Web Admin 模板语法与资源缺失 (Font/API),纠正启动引导的模块依赖路径。
- v1.2.3.1: 极致性能优化 - 深化 LazyImport 机制,实现 AI 库 (Gemini/OpenAI/Claude)、数据库 (DuckDB)、图像库 (PIL) 及数据处理 (Pandas) 的按需加载,大幅降低启动内存与耗时。
- v1.2.3.0: 阶段 9 完成 - 安全加固与审计体系。实现全链路审计日志 (AOP),增加 Web Admin IP 频率限制与访问控制。
- v1.2.2.9: CI 深度优化 - 修复单元测试超时问题,同步 CI 配置 (增加运行时长统计),修复 Auth CSRF 测试漏洞,增强 Mock 机制稳定性。
- v1.2.2.8: CI 稳定性修复 - 解决 GitHub CI 递归错误 (RecursionError)、增强本地 CI 诊断能力、同步云端 lint 排除规则。
- v1.2.2.7: 架构分层修复 - 移除 core 层对 handlers 层的非法依赖、修复未定义名称错误、通过本地 CI 质量门禁。

- v1.2.2.6: 代码质量治理 - Flake8 配置标准化、Lint 错误全面清理、临时目录排除规则建立。
- v1.2.2.5: 工程系统升级 - Local CI 技能集成、Git 自动化工作流强关联、架构守卫 (Arch Guard) 汉化与规则放宽。
- v1.2.2.4: 关键修复 - Web Admin 编码灾难恢复 (Encoding/Mojibake Fixes)、RSS 模块语法修复与健康度扫描 (Self-Healing)。
- v1.2.2.3: 架构重构 (Phase 6) - Web Admin 模块化 (Router/Handler Split)、UI 渲染器重构 (Facade/Strategy Pattern)、前端 API 解耦。
- v1.2.2.2: 架构重构 (Phase 5) - SessionManager 服务化下沉、ForwardSettings 独立解耦、全链路异步IO合规、静默失败治理完成。
- v1.2.2.1: 架构重构 (Phase 4) - 动态过滤链、MenuController 治理、RSS 模块归口统一。
- v1.2.2: 架构重构 (Phase 3+) - 核心流水线集成测试覆盖、模型字段补全、重试机制增强。
- v1.2.1: Phase 3 完成 - DTO 强制转换、common.py 清理、查询/过滤逻辑分层。
- v1.2.0: 核心架构重构(Phase 3) - 模型拆分、服务分层、DB迁移引入。
- v1.1.0: Phase 2 Cleanups.
- v1.0.0: Initial release.
"""

def get_version():
    return VERSION

def get_latest_changelog():
    """获取最近的一个版本记录"""
    lines = UPDATE_INFO.strip().splitlines()
    if lines and "**更新日志**" in lines[0]:
        lines = lines[1:]
    
    latest = []
    for line in lines:
        if line.startswith("- v"):
            if latest: break
            latest.append(line)
        elif latest:
            latest.append(line)
    return "\n".join(latest)

WELCOME_TEXT = f"""
🚀 **TG ONE 系统 v{VERSION}**

**最新更新:**
{get_latest_changelog()}

...
使用 /changelog 查看完整日志
使用 /menu 唤起主菜单
"""
