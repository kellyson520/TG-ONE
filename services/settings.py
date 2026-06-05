"""已弃用的配置模块，现在使用 core/config.py 替代"""
from core.config import settings

# 为了兼容旧代码，提供一个 Settings 类的别名
Settings = type(settings)