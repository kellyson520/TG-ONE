import logging
from typing import Any
from core.config import settings

logger = logging.getLogger(__name__)

class SettingsApplier:
    """
    负责将后台配置页面的修改应用到运行时配置对象 (settings)。
    同时处理一些特殊的副作用（如修改日志级别）。
    """
    def apply(self, key: str, value: Any) -> None:
        # 1. 更新全局 settings 对象
        if hasattr(settings, key):
            try:
                # 尝试设置属性，Pydantic BaseSettings (frozen=False) 允许直接设置
                setattr(settings, key, value)
            except Exception as e:
                logger.error(f"无法应用配置项 {key}={value}: {e}")

        # 2. 处理特殊的运行时副作用 (比如 logging 级别这种不是单靠属性就能改变的)
        if key == 'LOG_LEVEL':
            try:
                lvl_str = str(value).upper()
                lvl = getattr(logging, lvl_str, logging.INFO)
                logging.getLogger().setLevel(lvl)
                # 同时更新核心处理器的级别 (如果有的话)
            except Exception as e:
                logger.warning(f"无法设置日志级别 {value}: {e}")
        
        elif key == 'TELETHON_LOG_LEVEL':
            try:
                # Telethon 可能会在 settings 更新后由它自己的逻辑读取，
                # 但这里我们也可以记录一下。
                pass
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

        # 提示：不再同步更新 os.environ，强制所有模块使用 core.config.settings 获取配置。

settings_applier = SettingsApplier()
