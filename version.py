VERSION = "1.2.2.8"

WELCOME_TEXT = """
👋 欢迎使用 Telegram 消息转发机器人！

📱 当前版本：v{version}

📖 查看完整命令列表请使用 /help
""".format(version=VERSION)

UPDATE_INFO = """
**更新日志**
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
