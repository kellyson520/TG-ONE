"""
全局转发筛选与媒体设置服务层
负责全局媒体设置的加载、保存与更新
"""
from typing import Dict, Any, List, Optional
import logging
import json
from datetime import datetime
from sqlalchemy import select

from models.models import SystemConfiguration
from repositories.db_context import async_db_session

logger = logging.getLogger(__name__)


class ForwardSettingsService:
    def __init__(self):
        self._global_settings = None

    async def _load_global_settings(self) -> Dict[str, Any]:
        """从数据库加载全局设置"""
        if self._global_settings is not None:
            return self._global_settings

        # 默认设置
        default_settings = {
            "media_types": {
                "image": True,
                "video": True,
                "audio": True,
                "voice": True,
                "document": True,
            },
            "allow_text": True,
            "allow_emoji": True,
            "only_text": False,
            "only_media": False,
            "media_extension_enabled": False,
            "extension_filter_mode": "blacklist",
            "media_extensions": [],
            "media_duration_enabled": False,
            "duration_min_seconds": 0,
            "duration_max_seconds": 0,
            "media_size_filter_enabled": False,
            "media_size_alert_enabled": False,
            "media_size_limit": 100,
            "media_size_limit_kb": 0,
            "include_keywords": [],
            "exclude_keywords": [],
        }

        async with async_db_session() as session:
            try:
                result = await session.execute(
                    select(SystemConfiguration).filter(
                        SystemConfiguration.key == "global_media_settings"
                    )
                )
                config = result.scalar_one_or_none()

                if config and config.value:
                    try:
                        saved_settings = json.loads(config.value)
                        default_settings.update(saved_settings)
                    except Exception as e:
                        logger.error(f"解析全局设置失败: {str(e)}")
            except Exception as e:
                logger.error(f"从数据库加载设置失败: {e}")

            self._global_settings = default_settings
            return self._global_settings

    async def _save_global_settings(self):
        """保存全局设置到数据库"""
        if self._global_settings is None:
            return

        async with async_db_session() as session:
            try:
                result = await session.execute(
                    select(SystemConfiguration).filter(
                        SystemConfiguration.key == "global_media_settings"
                    )
                )
                config = result.scalar_one_or_none()

                if not config:
                    config = SystemConfiguration(
                        key="global_media_settings", data_type="json"
                    )
                    session.add(config)

                config.value = json.dumps(self._global_settings)
                config.updated_at = datetime.now().isoformat()
                await session.commit()

            except Exception as e:
                await session.rollback()
                logger.error(f"保存全局设置失败: {str(e)}")

    async def get_global_media_settings(self) -> Dict[str, Any]:
        """获取全局媒体设置"""
        return await self._load_global_settings()

    async def update_global_media_setting(self, key: str, value: Any) -> bool:
        """更新全局媒体设置"""
        settings = await self._load_global_settings()
        if key in settings:
            settings[key] = value
            await self._save_global_settings()
            self._global_settings = None # Invalidate cache
            return True
        elif key in settings.get("media_types", {}):
            settings["media_types"][key] = value
            await self._save_global_settings()
            self._global_settings = None
            return True
        return False

    async def toggle_media_type(self, media_type: str) -> bool:
        settings = await self._load_global_settings()
        if media_type in settings["media_types"]:
            current = settings["media_types"][media_type]
            new_state = not current
            settings["media_types"][media_type] = new_state
            await self._save_global_settings()
            self._global_settings = None
            return True
        return False

    async def get_duration_settings(self) -> Dict[str, Any]:
        settings = await self._load_global_settings()
        return {
            "enabled": bool(settings.get("media_duration_enabled", False)),
            "min_seconds": int(settings.get("duration_min_seconds", 0) or 0),
            "max_seconds": int(settings.get("duration_max_seconds", 0) or 0),
        }

    async def set_duration_component(self, side: str, unit: str, value: int) -> bool:
        settings = await self._load_global_settings()
        min_seconds = int(settings.get("duration_min_seconds", 0) or 0)
        max_seconds = int(settings.get("duration_max_seconds", 0) or 0)

        def seconds_to_components(total: int):
            if total < 0: total = 0
            days = total // 86400
            hours = (total % 86400) // 3600
            minutes = (total % 3600) // 60
            seconds = total % 60
            return days, hours, minutes, seconds

        def components_to_seconds(d, h, m, s):
            return max(0, int(d)*86400 + int(h)*3600 + int(m)*60 + int(s))

        min_d, min_h, min_m, min_s = seconds_to_components(min_seconds)
        max_d, max_h, max_m, max_s = seconds_to_components(max_seconds)

        if side == "min":
            if unit == "days": min_d = value
            elif unit == "hours": min_h = value
            elif unit == "minutes": min_m = value
            elif unit == "seconds": min_s = value
            min_seconds = components_to_seconds(min_d, min_h, min_m, min_s)
        else:
            if unit == "days": max_d = value
            elif unit == "hours": max_h = value
            elif unit == "minutes": max_m = value
            elif unit == "seconds": max_s = value
            max_seconds = components_to_seconds(max_d, max_h, max_m, max_s)

        try:
            settings["duration_min_seconds"] = min_seconds
            settings["duration_max_seconds"] = max_seconds
            await self._save_global_settings()
            self._global_settings = None
            return True
        except Exception as e:
            logger.error(f"保存时长区间失败: {str(e)}")
            return False

    async def toggle_media_extension(self, ext: str) -> bool:
        settings = await self._load_global_settings()
        extension = (ext or "").lower().strip()
        if not extension: return None
        selected = settings.get("media_extensions", [])
        if extension in selected:
            selected.remove(extension)
        else:
            selected.append(extension)
        
        settings["media_extensions"] = sorted(list(set(selected)))
        await self._save_global_settings()
        self._global_settings = None
        return extension in settings["media_extensions"]

    async def set_media_size_limit(self, limit_mb: int) -> bool:
        return await self.update_global_media_setting("media_size_limit", int(limit_mb))

    async def toggle_global_boolean(self, key: str) -> Dict[str, Any]:
        """通用布尔开关切换，返回新值"""
        try:
            settings = await self.get_global_media_settings()
            current = bool(settings.get(key, False))
            new_value = not current
            ok = await self.update_global_media_setting(key, new_value)
            return {'success': ok, 'new_value': new_value}
        except Exception as e:
            logger.error(f"通用布尔开关切换失败({key}): {e}")
            return {'success': False, 'new_value': None}

    async def toggle_extension_mode(self) -> Dict[str, Any]:
        try:
            settings = await self.get_global_media_settings()
            current_mode = settings.get('extension_filter_mode', 'blacklist')
            new_mode = 'whitelist' if current_mode == 'blacklist' else 'blacklist'
            ok = await self.update_global_media_setting('extension_filter_mode', new_mode)
            return {'success': ok, 'new_mode': new_mode}
        except Exception as e:
            logger.error(f"切换扩展模式失败: {e}")
            return {'success': False, 'new_mode': None}

    async def get_media_extensions_options(self) -> List[str]:
        """获取可选的媒体扩展名列表（优先从配置加载）"""
        try:
            from utils.core.settings import load_media_extensions
            options = load_media_extensions()
            if isinstance(options, list) and options:
                return options
        except Exception:
            pass
        return ["jpg", "jpeg", "png", "gif", "webp", "mp4", "mkv", "mov", "avi", "mp3", "flac", "wav", "ogg", "zip", "rar", "7z", "pdf", "docx"]

forward_settings_service = ForwardSettingsService()


