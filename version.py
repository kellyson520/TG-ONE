VERSION = "1.2.3.9"

UPDATE_INFO = """
**更新日志**
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
