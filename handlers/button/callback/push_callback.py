import traceback
import asyncio
import logging
from core.config import settings
from telethon import Button
from telethon.tl import types

from core.container import container
from core.helpers.common import is_admin
from ui.constants import PUSH_SETTINGS_TEXT
from handlers.button.button_helpers import (
    create_push_config_details_buttons,
    create_push_settings_buttons,
)
from services.session_service import session_manager

logger = logging.getLogger(__name__)


async def handle_push_callback(event, **kwargs):
    """处理推送设置相关回调 (异步版) - Refactored to use Strategy Registry"""
    try:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        action = parts[0]

        from handlers.button.strategies import MenuHandlerRegistry

        if await MenuHandlerRegistry.dispatch(event, action, data=data, **kwargs):
            return

        logger.warning(f"PushCallback: No strategy found for action {action}")
        await event.answer("⚠️ 未知指令", alert=True)

    except Exception as e:
        logger.error(f"处理推送回调失败: {e}", exc_info=True)
        await event.answer("⚠️ 系统繁忙", alert=True)


async def callback_push_settings(event, rule_id, session, message, data):
    try:
        await event.edit(
            PUSH_SETTINGS_TEXT,
            buttons=await create_push_settings_buttons(rule_id=int(rule_id)),
            link_preview=False,
        )
    except Exception as e:
        logger.error(f"加载推送设置失败: {e}")
        await event.answer("⚠️ 加载失败")
    return


async def callback_toggle_enable_push(event, rule_id, session, message, data):
    """处理切换推送启用状态的回调"""
    try:
        # 使用 Service 处理通用设置切换和同步
        res = await container.rule_service.toggle_rule_setting(int(rule_id), "enable_push")
        
        if res.get("success"):
            await event.edit(
                PUSH_SETTINGS_TEXT,
                buttons=await create_push_settings_buttons(int(rule_id)),
                link_preview=False,
            )
            status = "启用" if res.get("new_value") else "禁用"
            await event.answer(f"已{status}推送功能")
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换推送状态失败: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_add_push_channel(event, rule_id, session, message, data):
    """处理添加推送配置的回调"""
    try:
        # 鉴权
        if isinstance(event.chat, types.Channel):
            if not await is_admin(event):
                await event.answer("只有管理员可以修改设置")
                return
            user_id = settings.USER_ID
        else:
            user_id = event.sender_id

        # 设置用户状态
        chat_id = event.chat_id
        state = f"add_push_channel:{rule_id}"

        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "push",
            "timestamp": session_manager._get_timestamp(),
        }

        # 启动超时取消任务 (复用 ai_callback 的逻辑，实际上它是通用的)
        from handlers.button.callback.ai_callback import cancel_state_after_timeout
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))

        await message.edit(
            f"请发送推送配置\n" f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_add_push_channel:{rule_id}")]],
        )

    except Exception as e:
        logger.error(f"进入添加推送频道状态失败: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_cancel_add_push_channel(event, rule_id, session, message, data):
    """取消添加推送配置"""
    try:
        rule_id_val = data.split(":")[1]
        
        # 清除状态
        if isinstance(event.chat, types.Channel):
            user_id = settings.USER_ID
        else:
            user_id = event.sender_id

        chat_id = event.chat_id
        if user_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[user_id]:
                session_manager.user_sessions[user_id].pop(chat_id)

        await event.edit(
            PUSH_SETTINGS_TEXT,
            buttons=await create_push_settings_buttons(int(rule_id_val)),
            link_preview=False,
        )
        await event.answer("已取消添加推送配置")
    except Exception as e:
        logger.error(f"取消添加推送频道失败: {e}")
    return


async def callback_toggle_push_config(event, config_id, session, message, data):
    """处理点击推送配置的回调"""
    try:
        # 这里的 config_id 是 data 里的 config_id
        configs = await container.rule_repo.get_push_configs(config_id=int(config_id))
        if not configs:
            await event.answer("推送配置不存在")
            return
        
        config = configs[0]

        await event.edit(
            f"推送配置: `{config.push_channel}`\n",
            buttons=await create_push_config_details_buttons(config.id),
        )
    except Exception as e:
        logger.error(f"加载推送配置详情失败: {e}")
        await event.answer("⚠️ 加载失败")
    return


async def callback_toggle_push_config_status(event, config_id, session, message, data):
    """处理切换推送配置状态的回调"""
    try:
        # 使用 Service 处理切换和同步
        res = await container.rule_service.toggle_push_status_by_config(int(config_id))
        
        if res.get("success"):
            configs = await container.rule_repo.get_push_configs(config_id=int(config_id))
            config = configs[0]
            await event.edit(
                f"推送配置: `{config.push_channel}`\n",
                buttons=await create_push_config_details_buttons(config.id),
            )
            status = "启用" if res.get("new_value") else "禁用"
            await event.answer(f"已{status}推送配置")
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换推送频道状态失败: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_delete_push_config(event, config_id, session, message, data):
    """处理删除推送配置的回调"""
    try:
        # 先获取 rule_id 用于返回
        configs = await container.rule_repo.get_push_configs(config_id=int(config_id))
        if not configs:
            await event.answer("配置已不存在")
            return
            
        rule_id = configs[0].rule_id

        # 使用 Service 彻底删除并同步
        res = await container.rule_service.delete_push_config(int(config_id))
        
        if res.get("success"):
            await event.edit(
                PUSH_SETTINGS_TEXT,
                buttons=await create_push_settings_buttons(int(rule_id)),
                link_preview=False,
            )
            await event.answer("已删除推送配置")
        else:
            await event.answer(f"❌ 删除失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"删除推送配置失败: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return


async def callback_push_page(event, rule_id_data, session, message, data):
    """处理推送设置页面翻页的回调"""
    try:
        parts = rule_id_data.split(":")
        rule_id = int(parts[0])
        page = int(parts[1])

        await event.edit(
            PUSH_SETTINGS_TEXT,
            buttons=await create_push_settings_buttons(rule_id, page),
            link_preview=False,
        )
        await event.answer(f"第 {page+1} 页")
    except Exception as e:
        logger.error(f"翻页失败: {e}")
    return


async def callback_toggle_enable_only_push(event, rule_id, session, message, data):
    """处理切换只转发到推送配置的回调"""
    try:
        # 使用 Service 处理通用设置切换和同步
        res = await container.rule_service.toggle_rule_setting(int(rule_id), "enable_only_push")
        
        if res.get("success"):
            await event.edit(
                PUSH_SETTINGS_TEXT,
                buttons=await create_push_settings_buttons(int(rule_id)),
                link_preview=False,
            )
            status = "启用" if res.get("new_value") else "禁用"
            await event.answer(f"已{status}只转发到推送配置")
        else:
            await event.answer(f"❌ 切换失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"切换只转发推送状态失败: {e}")
        await event.answer("⚠️ 操作失败")
    return


async def callback_toggle_media_send_mode(event, config_id, session, message, data):
    """处理切换媒体发送方式的回调"""
    try:
        # 先获取当前模式
        configs = await container.rule_repo.get_push_configs(config_id=int(config_id))
        if not configs:
            await event.answer("配置不存在")
            return
            
        config = configs[0]
        new_mode = "Multiple" if config.media_send_mode == "Single" else "Single"
        
        # 使用 Service 处理更新和同步
        res = await container.rule_service.update_push_config_setting(int(config_id), "media_send_mode", new_mode)
        
        if res.get("success"):
            mode_text = "全部" if new_mode == "Multiple" else "单个"
            await event.edit(
                f"推送配置: `{config.push_channel}`\n",
                buttons=await create_push_config_details_buttons(int(config_id)),
            )
            await event.answer(f"已设置媒体发送方式为: {mode_text}")
        else:
            await event.answer(f"❌ 设置失败: {res.get('error')}")
    except Exception as e:
        logger.error(f"设置媒体发送模式失败: {e}", exc_info=True)
        await event.answer("⚠️ 操作失败")
    return
