"""
新菜单系统的回调处理器
"""
import traceback
import logging
from core.container import container
from handlers.button.strategies import MenuHandlerRegistry

logger = logging.getLogger(__name__)

# [MIGRATED] Standalone functions moved to handlers/button/strategies/settings.py
# - handle_toggle_setting
# - handle_toggle_extension_mode
# - handle_toggle_media_type
# - handle_toggle_media_duration
# - handle_set_duration_*
# - handle_save_duration_settings
# - handle_toggle_media_size_*

async def handle_new_menu_callback(event, **kwargs):
    """处理新菜单回调 (统一入口)"""
    try:
        data = event.data.decode("utf-8")
        if not data.startswith("new_menu:"):
            return

        action_data = data[9:]  # 去掉 'new_menu:' 前缀
        
        # 获取消息上下文用于向下兼容
        message = await event.get_message()
        
        # [PHASE 6] 彻底移除入口处的 session 创建
        await callback_new_menu_handler(event, action_data, message, data)
    except Exception as e:
        logger.error(f"处理菜单回调失败: {e}", exc_info=True)
        await event.answer("⚠️ 系统繁忙，请稍后再试", alert=True)


async def callback_new_menu_handler(event, action_data, message, data):
    """新菜单系统的统一回调处理器"""
    try:
        try:
            logger.info(f"[menu] new_menu action_data={action_data}")
        except Exception:
            pass

        # action_data 已经是解析后的动作
        if ":" in action_data:
            parts = action_data.split(":")
            action = parts[0]
            extra_data = parts[1:]
        else:
            action = action_data
            extra_data = []

        # Try to dispatch using the new Strategy Pattern
        context = {
            "extra_data": extra_data,
            "message": message,
            "data": data,
            "action_data": action_data
        }
        
        if await MenuHandlerRegistry.dispatch(event, action, **context):
            return

        logger.warning(f"[Legacy] Action not handled by any strategy: {action}")
        await event.answer("⚠️ 未知指令或功能迁移中", alert=True)

    except Exception as e:
        logger.error(f"菜单处理异常: {e}", exc_info=True)
        await event.answer("⚠️ 处理请求时发生错误", alert=True)
