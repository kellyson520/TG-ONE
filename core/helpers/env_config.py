"""
环境配置动态更新工具
支持运行时修改配置并持久化到env文件
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

from core.config import settings
# from services.config_service import config_service

logger = logging.getLogger(__name__)


class EnvConfigManager:
    """环境配置管理器"""

    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self._config_cache: Dict[str, str] = {}
        self._load_config()

    def _load_config(self):
        """加载配置文件到缓存"""
        try:
            if self.env_file.exists():
                with open(self.env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            self._config_cache[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

    def get_config(self, key: str, default: str = "") -> str:
        """获取配置（已废弃，建议直接使用 core.config.settings）"""
        logger.warning(
            f"EnvConfigManager.get_config() 已废弃，请使用 core.config.settings 获取配置: {key}"
        )
        # 优先从 settings 获取
        if hasattr(settings, key):
            return str(getattr(settings, key))
        # 回退到旧逻辑
        # 回退到旧逻辑
        try:
            mod = __import__('services.config_service', fromlist=['config_service'])
            config_service = mod.config_service
            v = config_service.get(key)
        except Exception:
            v = None
        if v is not None:
            return str(v)
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value
        return self._config_cache.get(key, default)

    def set_config(self, key: str, value: str, persist: bool = True) -> bool:
        """设置配置"""
        try:
            mod = __import__('services.config_service', fromlist=['config_service'])
            config_service = mod.config_service
            config_service.set(key, value, data_type="string")
            os.environ[key] = value
            self._config_cache[key] = value
            if persist:
                self._persist_config()
            return True
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
            return False

    def _persist_config(self):
        """持久化配置到文件"""
        try:
            if not self.env_file.exists():
                try:
                    self.env_file.touch()
                except Exception as e:
                    logger.error(f"无法创建 .env 文件: {e}")
                    return

            # 读取原文件内容
            lines = []
            with open(self.env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 更新配置行
            updated_keys = set()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in self._config_cache:
                        lines[i] = f"{key}={self._config_cache[key]}\n"
                        updated_keys.add(key)

            # 添加新的配置项（如果原文件中没有）
            for key, value in self._config_cache.items():
                if key not in updated_keys:
                    lines.append(f"{key}={value}\n")

            # 写回文件
            with open(self.env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            logger.info("配置已持久化到文件")

        except Exception as e:
            logger.error(f"持久化配置失败: {e}")

    def get_history_message_limit(self) -> int:
        """获取历史消息数量限制（已废弃，建议直接使用 settings.HISTORY_MESSAGE_LIMIT）"""
        logger.warning(
            f"EnvConfigManager.get_history_message_limit() 已废弃，请使用 core.config.settings.HISTORY_MESSAGE_LIMIT"
        )
        return settings.HISTORY_MESSAGE_LIMIT

    def set_history_message_limit(self, limit: int) -> bool:
        """设置历史消息数量限制"""
        try:
            return self.set_config("HISTORY_MESSAGE_LIMIT", str(max(0, limit)))
        except Exception as e:
            logger.error(f"设置历史消息数量限制失败: {e}")
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "total_configs": len(self._config_cache),
            "history_message_limit": self.get_history_message_limit(),
            "config_file": str(self.env_file),
            "file_exists": self.env_file.exists(),
        }


# 全局配置管理器实例
env_config_manager = EnvConfigManager()
