import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

class SettingsApplier:
    def apply(self, key: str, value: Any) -> None:
        if key == 'HISTORY_MESSAGE_LIMIT':
            os.environ['HISTORY_MESSAGE_LIMIT'] = str(value)
            return
        if key == 'LOG_LEVEL':
            try:
                lvl = getattr(logging, str(value).upper(), logging.INFO)
                logging.getLogger().setLevel(lvl)
            except Exception as e:
                logger.warning(f"Failed to set log level to {value}: {e}")
            return
        if key == 'LOG_FORMAT':
            os.environ['LOG_FORMAT'] = str(value)
            return
        if key == 'LOG_INCLUDE_TRACEBACK':
            os.environ['LOG_INCLUDE_TRACEBACK'] = 'true' if bool(value) else 'false'
            return
        if key == 'LOG_LANGUAGE':
            os.environ['LOG_LANGUAGE'] = str(value)
            return
        if key == 'LOG_LOCALIZE_MESSAGES':
            os.environ['LOG_LOCALIZE_MESSAGES'] = 'true' if bool(value) else 'false'
            return
        if key == 'LOG_COLOR':
            os.environ['LOG_COLOR'] = 'true' if bool(value) else 'false'
            return
        if key == 'LOG_DATETIME_FORMAT':
            os.environ['LOG_DATETIME_FORMAT'] = str(value)
            return
        if key == 'LOG_LOCALIZE_PREFIXES':
            os.environ['LOG_LOCALIZE_PREFIXES'] = str(value)
            return
        if key == 'TELETHON_LOG_LEVEL':
            try:
                os.environ['TELETHON_LOG_LEVEL'] = str(value).upper()
            except Exception as e:
                logger.warning(f"Failed to set telethon log level to {value}: {e}")
            return
        if key == 'LOG_PUSH_TG_ENABLE':
            os.environ['LOG_PUSH_TG_ENABLE'] = 'true' if bool(value) else 'false'
            return
        if key == 'LOG_PUSH_TG_LEVEL':
            os.environ['LOG_PUSH_TG_LEVEL'] = str(value).upper()
            return
        os.environ[key] = str(value)

settings_applier = SettingsApplier()
