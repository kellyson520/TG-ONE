"""
全局转发筛选与媒体设置服务层
封装 forward_manager 的配置读取与更新，供控制器与回调调用
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ForwardSettingsService:
    async def get_global_media_settings(self) -> Dict[str, Any]:
        try:
            from handlers.button.forward_management import forward_manager
            return await forward_manager.get_global_media_settings()
        except Exception as e:
            logger.error(f"获取全局媒体设置失败: {e}")
            return {}

    async def update_global_media_setting(self, key: str, value: Any) -> bool:
        try:
            from handlers.button.forward_management import forward_manager
            await forward_manager.update_global_media_setting(key, value)
            return True
        except Exception as e:
            logger.error(f"更新全局媒体设置失败({key}): {e}")
            return False

    async def toggle_media_type(self, media_type: str) -> bool:
        try:
            from handlers.button.forward_management import forward_manager
            return await forward_manager.toggle_media_type(media_type)
        except Exception as e:
            logger.error(f"切换媒体类型失败({media_type}): {e}")
            return False

    async def get_duration_settings(self) -> Dict[str, Any]:
        try:
            from handlers.button.forward_management import forward_manager
            return await forward_manager.get_duration_settings()
        except Exception as e:
            logger.error(f"获取时长设置失败: {e}")
            return {}

    async def set_duration_component(self, side: str, unit: str, value: int) -> bool:
        try:
            from handlers.button.forward_management import forward_manager
            return await forward_manager.set_duration_component(side, unit, value)
        except Exception as e:
            logger.error(f"设置时长分量失败: {e}")
            return False

    async def toggle_media_extension(self, ext: str) -> bool:
        try:
            from handlers.button.forward_management import forward_manager
            return await forward_manager.toggle_media_extension(ext)
        except Exception as e:
            logger.error(f"切换媒体扩展失败: {e}")
            return False

    async def set_media_size_limit(self, val: int) -> bool:
        try:
            from handlers.button.forward_management import forward_manager
            return await forward_manager.set_media_size_limit(val)
        except Exception as e:
            logger.error(f"设置媒体大小上限失败: {e}")
            return False

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


forward_settings_service = ForwardSettingsService()


