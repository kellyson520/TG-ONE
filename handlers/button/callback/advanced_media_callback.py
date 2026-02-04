"""
高级媒体筛选回调处理器 (原生异步版)
"""

import logging
from telethon import Button
from telethon.tl import types
from core.config import settings

from services.session_service import session_manager
from core.container import container
from models.models import ForwardRule

logger = logging.getLogger(__name__)


async def handle_advanced_media_callback(event, **kwargs):
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

    # 创建异步session
    async with container.db.session() as session:
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
        # 兼容新菜单的组件调用
        elif action == "open_duration_picker":
            # 逻辑可能需要根据实际组件调整，暂留空或实现基础跳转
            await event.answer("功能开发中...")


async def callback_toggle_duration_filter(event, rule_id, session, message, data):
    try:
        rule = await session.get(ForwardRule, rule_id)
        if not rule:
            await event.answer("规则不存在", alert=True)
            return

        rule.enable_duration_filter = not getattr(rule, "enable_duration_filter", False)
        await session.commit()

        status = "开启" if rule.enable_duration_filter else "关闭"
        await event.answer(f"时长过滤已{status}")

        from .media_callback import _show_rule_media_settings

        await _show_rule_media_settings(event, rule_id)

    except Exception as e:
        logger.error(f"切换时长过滤失败: {e}")
        await event.answer("操作失败", alert=True)


async def callback_set_duration_range(event, rule_id, session, message, data):
    try:
        rule = await session.get(ForwardRule, rule_id)
        if not rule:
            await event.answer("规则不存在", alert=True)
            return

        chat = await event.get_chat()
        # 处理频道ID差异
        if isinstance(chat, types.Channel):
            user_id = settings.USER_ID
            chat_id = int(f"100{abs(chat.id)}")
        else:
            user_id = int(event.sender_id)
            chat_id = event.chat_id

        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": "waiting_duration_range",
            "message": {"rule_id": rule_id},
            "state_type": "advanced_media",
        }

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
        logger.error(f"设置时长范围失败: {e}")
        await event.answer("操作失败", alert=True)


async def callback_cancel_set_duration_range(event, rule_id, session, message, data):
    try:
        chat = await event.get_chat()
        if isinstance(chat, types.Channel):
            user_id = settings.USER_ID
            chat_id = int(f"100{abs(chat.id)}")
        else:
            user_id = int(event.sender_id)
            chat_id = event.chat_id

        # 使用 session_manager 替代 state_manager
        if user_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[user_id]:
                session_manager.user_sessions[user_id].pop(chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not session_manager.user_sessions[user_id]:
                    session_manager.user_sessions.pop(user_id)

        from .media_callback import _show_rule_media_settings

        await _show_rule_media_settings(event, rule_id)

    except Exception as e:
        logger.error(f"取消设置失败: {e}")


async def callback_toggle_resolution_filter(event, rule_id, session, message, data):
    try:
        rule = await session.get(ForwardRule, rule_id)
        if not rule:
            return

        rule.enable_resolution_filter = not getattr(
            rule, "enable_resolution_filter", False
        )
        await session.commit()

        status = "开启" if rule.enable_resolution_filter else "关闭"
        await event.answer(f"分辨率过滤已{status}")

        from .media_callback import _show_rule_media_settings

        await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.error(f"切换分辨率过滤失败: {e}")


async def callback_set_resolution_range(event, rule_id, session, message, data):
    try:
        rule = await session.get(ForwardRule, rule_id)
        if not rule:
            return

        chat = await event.get_chat()
        if isinstance(chat, types.Channel):
            user_id = settings.USER_ID
            chat_id = int(f"100{abs(chat.id)}")
        else:
            user_id = int(event.sender_id)
            chat_id = event.chat_id

        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": "waiting_resolution_range",
            "message": {"rule_id": rule_id},
            "state_type": "advanced_media",
        }

        text = "📐 **设置分辨率**\n请输入: `minW minH [maxW maxH]`"
        buttons = [[Button.inline("❌ 取消", f"cancel_set_resolution_range:{rule_id}")]]
        await event.edit(text, buttons=buttons, parse_mode="markdown")
    except Exception:
        await event.answer("操作失败", alert=True)


async def callback_cancel_set_resolution_range(event, rule_id, session, message, data):
    # 逻辑同 cancel_set_duration_range
    try:
        chat = await event.get_chat()
        if isinstance(chat, types.Channel):
            user_id = settings.USER_ID
            chat_id = int(f"100{abs(chat.id)}")
        else:
            user_id = int(event.sender_id)
            chat_id = event.chat_id
        # 使用 session_manager 替代 state_manager
        if user_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[user_id]:
                session_manager.user_sessions[user_id].pop(chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not session_manager.user_sessions[user_id]:
                    session_manager.user_sessions.pop(user_id)
        from .media_callback import _show_rule_media_settings

        await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')


async def callback_toggle_file_size_range_filter(event, rule_id, session, message, data):
    try:
        rule = await session.get(ForwardRule, rule_id)
        if rule:
            rule.enable_file_size_range = not getattr(
                rule, "enable_file_size_range", False
            )
            await session.commit()
            await event.answer(
                f"大小过滤已{'开启' if rule.enable_file_size_range else '关闭'}"
            )
            from .media_callback import _show_rule_media_settings

            await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.error(f"Size filter toggle error: {e}")


async def callback_set_file_size_range(event, rule_id, session, message, data):
    try:
        rule = await session.get(ForwardRule, rule_id)
        if not rule:
            return

        chat = await event.get_chat()
        if isinstance(chat, types.Channel):
            user_id = settings.USER_ID
            chat_id = int(f"100{abs(chat.id)}")
        else:
            user_id = int(event.sender_id)
            chat_id = event.chat_id

        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": "waiting_file_size_range",
            "message": {"rule_id": rule_id},
            "state_type": "advanced_media",
        }

        text = "💾 **设置文件大小**\n请输入: `min [max]` (支持K/M/G)"
        buttons = [[Button.inline("❌ 取消", f"cancel_set_file_size_range:{rule_id}")]]
        await event.edit(text, buttons=buttons, parse_mode="markdown")
    except Exception as e:
        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')


async def callback_cancel_set_file_size_range(event, rule_id, session, message, data):
    try:
        chat = await event.get_chat()
        if isinstance(chat, types.Channel):
            user_id = settings.USER_ID
            chat_id = int(f"100{abs(chat.id)}")
        else:
            user_id = int(event.sender_id)
            chat_id = event.chat_id
        # 使用 session_manager 替代 state_manager
        if user_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[user_id]:
                session_manager.user_sessions[user_id].pop(chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not session_manager.user_sessions[user_id]:
                    session_manager.user_sessions.pop(user_id)
        from .media_callback import _show_rule_media_settings

        await _show_rule_media_settings(event, rule_id)
    except Exception as e:
        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
