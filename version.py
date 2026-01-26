VERSION = "1.2.2.2"

WELCOME_TEXT = """
👋 欢迎使用 Telegram 消息转发机器人！

📱 当前版本：v{version}

📖 查看完整命令列表请使用 /help
""".format(version=VERSION)

UPDATE_INFO = """
**更新日志**
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
