VERSION = "1.2.0"

WELCOME_TEXT = """
👋 欢迎使用 Telegram 消息转发机器人！

📱 当前版本：v{version}

📖 查看完整命令列表请使用 /help
""".format(version=VERSION)

UPDATE_INFO = """
**更新日志**
- v1.2.0: 核心架构重构(Phase 3) - 模型拆分、服务分层、DB迁移引入。
- v1.1.0: Phase 2 Cleanups.
- v1.0.0: Initial release.
"""

def get_version():
    return VERSION
