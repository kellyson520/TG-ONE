"""
高级媒体筛选回调处理器 (原生异步版)
"""

import logging
from telethon import Button
from telethon.tl import types
from core.config import settings

from services.session_service import session_manager
from core.container import container

logger = logging.getLogger(__name__)


async def handle_advanced_media_callback(event, session=None, **kwargs):
    """高级媒体筛选回调分发入口"""
    data = event.data.decode("utf-8")
    # 格式通常是 action:rule_id 或 action:rule_id:extra
    parts = data.split(":")
    action = parts[0]

    try:
        rule_id = int(parts[1])
    except (IndexError, ValueError):
        await event.answer("无效的规则ID", alert=True)
        return

    if action == "toggle_duration_filter":
        await callback_toggle_duration_filter(event, rule_id, session, None, data)
    elif action == "set_duration_range":
        await callback_set_duration_range(event, rule_id, session, None, data)
    elif action == "cancel_set_duration_range":
        await callback_cancel_set_duration_range(event, rule_id, session, None, data)
    elif action == "toggle_resolution_filter":
        await callback_toggle_resolution_filter(event, rule_id, session, None, data)
    elif action == "set_resolution_range":
        await callback_set_resolution_range(event, rule_id, session, None, data)
    elif action == "cancel_set_resolution_range":
        await callback_cancel_set_resolution_range(event, rule_id, session, None, data)
    elif action == "toggle_file_size_range_filter":
        await callback_toggle_file_size_range_filter(event, rule_id, session, None, data)
    elif action == "set_file_size_range":
        await callback_set_file_size_range(event, rule_id, session, None, data)
    elif action == "cancel_set_file_size_range":
        await callback_cancel_set_file_size_range(event, rule_id, session, None, data)
    elif action == "open_duration_picker":
        await event.answer("功能开发中...")


async def callback_toggle_duration_filter(event, rule_id, session, message, data):
    """切换时长过滤"""
    try:
        # 使用 Service 层处理切换逻辑
        res = await container.rule_service.toggle_rule_setting(rule_id, "enable_duration_filter")
        
        if res.get('success'):
            status = "开启" if res.get('new_value') else "关闭"
            await event.answer(f"✅ 时长过滤已{status}")
            from .media_callback import _show_rule_media_settings
            await _show_rule_media_settings(event, rule_id, session=None)
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}", alert=True)

    except Exception as e:
        logger.error(f"切换时长过滤失败: {e}")
        await event.answer("⚠️ 操作失败", alert=True)


async def callback_set_duration_range(event, rule_id, session, message, data):
    """设置时长范围入口"""
    try:
        rule = await container.rule_repo.get_by_id(rule_id)
        if not rule:
            await event.answer("❌ 规则不存在", alert=True)
            return

        user_id = int(event.sender_id)
        chat_id = event.chat_id

        # 设置会话状态
        session_manager.set_user_session(user_id, chat_id, {
            "state": "waiting_duration_range",
            "rule_id": rule_id,
            "state_type": "advanced_media",
        })

        current_min = getattr(rule, "min_duration", 0)
        current_max = getattr(rule, "max_duration", 0)

        text = (
            "🎬 **设置时长范围**\n\n"
            f"当前: {current_min}s - {current_max if current_max > 0 else '∞'}s\n"
            "请输入: `最小` 或 `最小 最大` (0表示无限)\n例如: `30 300`"
        )
        buttons = [[Button.inline("❌ 取消", f"cancel_set_duration_range:{rule_id}")]]
        await event.edit(text, buttons=buttons, parse_mode="markdown")

    except Exception as e:
        logger.error(f"设置时长范围发起失败: {e}")
        await event.answer("⚠️ 操作失败", alert=True)


async def callback_cancel_set_duration_range(event, rule_id, session, message, data):
    """取消设置时长范围"""
    try:
        session_manager.clear_user_session(event.sender_id, event.chat_id)
        from .media_callback import _show_rule_media_settings
        await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.error(f"取消设置失败: {e}")


async def callback_toggle_resolution_filter(event, rule_id, session, message, data):
    """切换分辨率过滤"""
    try:
        res = await container.rule_service.toggle_rule_setting(rule_id, "enable_resolution_filter")
        if res.get('success'):
            status = "开启" if res.get('new_value') else "关闭"
            await event.answer(f"✅ 分辨率过滤已{status}")
            from .media_callback import _show_rule_media_settings
            await _show_rule_media_settings(event, rule_id)
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换分辨率过滤失败: {e}")


async def callback_set_resolution_range(event, rule_id, session, message, data):
    """设置分辨率入口"""
    try:
        session_manager.set_user_session(event.sender_id, event.chat_id, {
            "state": "waiting_resolution_range",
            "rule_id": rule_id,
            "state_type": "advanced_media",
        })

        text = "📐 **设置分辨率**\n请输入: `minW minH [maxW maxH]`"
        buttons = [[Button.inline("❌ 取消", f"cancel_set_resolution_range:{rule_id}")]]
        await event.edit(text, buttons=buttons, parse_mode="markdown")
    except Exception:
        await event.answer("⚠️ 操作失败", alert=True)


async def callback_cancel_set_resolution_range(event, rule_id, session, message, data):
    """取消设置分辨率"""
    try:
        session_manager.clear_user_session(event.sender_id, event.chat_id)
        from .media_callback import _show_rule_media_settings
        await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.error(f"取消设置分辨率失败: {e}")


async def callback_toggle_file_size_range_filter(event, rule_id, session, message, data):
    """切换文件大小范围过滤"""
    try:
        res = await container.rule_service.toggle_rule_setting(rule_id, "enable_file_size_range")
        if res.get('success'):
            await event.answer(f"✅ 大小过滤已{'开启' if res.get('new_value') else '关闭'}")
            from .media_callback import _show_rule_media_settings
            await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.error(f"Size filter toggle error: {e}")


async def callback_set_file_size_range(event, rule_id, session, message, data):
    """设置文件大小入口"""
    try:
        session_manager.set_user_session(event.sender_id, event.chat_id, {
            "state": "waiting_file_size_range",
            "rule_id": rule_id,
            "state_type": "advanced_media",
        })

        text = "💾 **设置文件大小**\n请输入: `min [max]` (支持K/M/G)"
        buttons = [[Button.inline("❌ 取消", f"cancel_set_file_size_range:{rule_id}")]]
        await event.edit(text, buttons=buttons, parse_mode="markdown")
    except Exception as e:
        logger.error(f"发起文件大小设置失败: {e}")
        await event.answer("⚠️ 操作失败", alert=True)


async def callback_cancel_set_file_size_range(event, rule_id, session, message, data):
    """取消设置文件大小"""
    try:
        session_manager.clear_user_session(event.sender_id, event.chat_id)
        from .media_callback import _show_rule_media_settings
        await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.error(f"取消大小设置失败: {e}")
