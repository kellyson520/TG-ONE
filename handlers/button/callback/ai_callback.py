import traceback
import asyncio
import logging
from core.config import settings
from telethon import Button
from telethon.tl import types

from services.session_service import session_manager
from core.container import container
from core.helpers.common import get_main_module, is_admin
from handlers.button.settings_manager import get_ai_settings_text

from handlers.button.button_helpers import (
    create_ai_settings_buttons,
    create_model_buttons,
    create_summary_time_buttons,
)

logger = logging.getLogger(__name__)


async def handle_ai_callback(event, **kwargs):
    """处理AI设置相关回调 (异步版) - Refactored to use Strategy Registry"""
    try:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        action = parts[0]

        from handlers.button.strategies import MenuHandlerRegistry

        if await MenuHandlerRegistry.dispatch(event, action, data=data, **kwargs):
            return

        logger.warning(f"AICallback: No strategy found for action {action}")
        await event.answer("⚠️ 未知指令", alert=True)

    except Exception as e:
        logger.error(f"处理AI回调失败: {e}", exc_info=True)
        await event.answer("⚠️ 系统繁忙", alert=True)


async def callback_ai_settings(event, rule_id, session, message, data):
    # 显示 AI 设置页面
    try:
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if rule:
            await event.edit(
                await get_ai_settings_text(rule),
                buttons=await create_ai_settings_buttons(rule),
            )
    except Exception as e:
        logger.error(f"加载AI设置失败: {e}")
        await event.answer("⚠️ 加载失败")
    return


async def callback_set_summary_time(event, rule_id, session, message, data):
    await event.edit(
        "请选择总结时间：", buttons=await create_summary_time_buttons(rule_id, page=0)
    )
    return


async def callback_set_summary_prompt(event, rule_id, session, message, data):
    """处理设置AI总结提示词的回调"""
    logger.info(f"开始处理设置AI总结提示词回调 - event: {event}, rule_id: {rule_id}")

    try:
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        user_id = event.sender_id
        chat_id = event.chat_id
        state = f"set_summary_prompt:{rule_id}"

        # 设置状态
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "ai",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        
        current_prompt = rule.summary_prompt or settings.DEFAULT_SUMMARY_PROMPT
        await message.edit(
            f"请发送新的AI总结提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前AI总结提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_summary:{rule_id}")]],
        )
    except Exception as e:
        logger.error(f"设置AI总结提示词状态失败: {e}")
        await event.answer("⚠️ 操作失败")
    return


async def cancel_state_after_timeout(
    user_id: int, chat_id: int, timeout_minutes: int = 5
):
    """在指定时间后自动取消状态"""
    await asyncio.sleep(timeout_minutes * 60)
    user_session = session_manager.user_sessions.get(user_id, {})
    chat_state = user_session.get(chat_id, {})
    current_state = chat_state.get("state")
    if current_state:  # 只有当状态还存在时才清除
        logger.info(f"状态超时自动取消 - user_id: {user_id}, chat_id: {chat_id}")
        user_session.pop(chat_id)
        if not user_session:
            session_manager.user_sessions.pop(user_id)


async def callback_set_ai_prompt(event, rule_id, session, message, data):
    """处理设置AI提示词的回调"""
    try:
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        user_id = event.sender_id
        chat_id = event.chat_id
        state = f"set_ai_prompt:{rule_id}"

        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "ai",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        
        current_prompt = rule.ai_prompt or settings.DEFAULT_AI_PROMPT
        await message.edit(
            f"请发送新的AI提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前AI提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_prompt:{rule_id}")]],
        )
    except Exception as e:
        logger.error(f"设置AI提示词状态失败: {e}")
        await event.answer("⚠️ 操作失败")
    return


async def callback_time_page(event, rule_id, session, message, data):
    parts = data.split(":")
    if len(parts) >= 3:
        _, rule_id, page = parts[:3]
        page = int(page)
        await event.edit(
            "请选择总结时间：",
            buttons=await create_summary_time_buttons(rule_id, page=page),
        )
    return


async def callback_select_time(event, rule_id, session, message, data):
    parts = data.split(":", 2)
    if len(parts) == 3:
        _, rule_id, time = parts
        logger.info(f"设置规则 {rule_id} 的总结时间为: {time}")
        try:
            # 使用 Service 层处理更新、同步和调度
            res = await container.rule_service.update_ai_setting(int(rule_id), "summary_time", time)
            
            if res.get("success"):
                # 获取最新 DTO 刷新界面
                rule = await container.rule_repo.get_by_id(int(rule_id))
                await event.edit(
                    await get_ai_settings_text(rule),
                    buttons=await create_ai_settings_buttons(rule),
                )
                logger.info("总结时间更新及界面刷新完成")
            else:
                await event.answer(f"❌ 更新失败: {res.get('error')}")
        except Exception as e:
            logger.error(f"设置总结时间时出错: {str(e)}", exc_info=True)
            await event.answer("⚠️ 设置失败")
    return


async def callback_select_model(event, rule_id, session, message, data):
    parts = data.split(":", 2)
    if len(parts) == 3:
        _, rule_id_part, model = parts
        try:
            # 使用 Service 层处理更新和同步
            res = await container.rule_service.update_ai_setting(int(rule_id_part), "ai_model", model)
            
            if res.get("success"):
                rule = await container.rule_repo.get_by_id(int(rule_id_part))
                await event.edit(
                    await get_ai_settings_text(rule),
                    buttons=await create_ai_settings_buttons(rule),
                )
                logger.info(f"已更新规则 {rule_id_part} 的AI模型为: {model}")
            else:
                await event.answer(f"❌ 更新失败: {res.get('error')}")
        except Exception as e:
            logger.error(f"设置AI模型时出错: {str(e)}", exc_info=True)
            await event.answer("⚠️ 设置失败")
    return


async def callback_model_page(event, rule_id, session, message, data):
    # 处理翻页
    parts = data.split(":")
    if len(parts) >= 3:
        _, rule_id, page = parts[:3]
        page = int(page)
        await event.edit(
            "请选择AI模型：", buttons=await create_model_buttons(rule_id, page=page)
        )
    return


async def callback_change_model(event, rule_id, session, message, data):
    await event.edit(
        "请选择AI模型：", buttons=await create_model_buttons(rule_id, page=0)
    )


async def callback_cancel_set_prompt(event, rule_id, session, message, data):
    # 处理取消设置提示词
    parts = data.split(":")
    if len(parts) >= 2:
        rule_id = parts[1]
        try:
            rule = await container.rule_repo.get_by_id(int(rule_id))
            if rule:
                # 清除状态
                user_id = event.sender_id
                chat_id = event.chat_id
                if user_id in session_manager.user_sessions:
                    if chat_id in session_manager.user_sessions[user_id]:
                        session_manager.user_sessions[user_id].pop(chat_id)
                        if not session_manager.user_sessions[user_id]:
                            session_manager.user_sessions.pop(user_id)
                # 返回到 AI 设置页面
                await event.edit(
                    await get_ai_settings_text(rule),
                    buttons=await create_ai_settings_buttons(rule),
                )
                await event.answer("已取消设置")
        except Exception as e:
            logger.error(f"取消设置提示词出错: {e}")
    return


async def callback_cancel_set_summary(event, rule_id, session, message, data):
    # 处理取消设置总结
    parts = data.split(":")
    if len(parts) >= 2:
        rule_id = parts[1]
        try:
            rule = await container.rule_repo.get_by_id(int(rule_id))
            if rule:
                # 清除状态
                user_id = event.sender_id
                chat_id = event.chat_id
                if user_id in session_manager.user_sessions:
                    if chat_id in session_manager.user_sessions[user_id]:
                        session_manager.user_sessions[user_id].pop(chat_id)
                        if not session_manager.user_sessions[user_id]:
                            session_manager.user_sessions.pop(user_id)
                # 返回到 AI 设置页面
                await event.edit(
                    await get_ai_settings_text(rule),
                    buttons=await create_ai_settings_buttons(rule),
                )
                await event.answer("已取消设置")
        except Exception as e:
            logger.error(f"取消设置总结出错: {e}")
    return


async def callback_summary_now(event, rule_id, session, message, data):
    # 处理立即执行总结的回调
    logger.info(f"处理立即执行总结回调 - rule_id: {rule_id}")

    try:
        # 使用 Repository 获取基本信息并验证
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        # 使用 Service 启动立即总结任务
        res = await container.rule_service.summary_now(int(rule_id))
        
        if res.get("success"):
            await event.answer("开始执行总结，请稍候...")
            
            source_name = rule.source_chat.name if rule.source_chat else "未知"
            target_name = rule.target_chat.name if rule.target_chat else "未知"
            
            await message.edit(
                f"正在为规则 {rule_id}（{source_name} -> {target_name}）生成总结...\n"
                f"处理需要一定时间，请耐心等待。",
                buttons=[[Button.inline("返回", f"ai_settings:{rule_id}")]],
            )
            logger.info(f"已启动规则 {rule_id} 的立即总结任务")
        else:
             await event.answer(f"❌ 启动总结失败: {res.get('error')}")
             
    except Exception as e:
        logger.error(f"处理立即总结出错: {str(e)}", exc_info=True)
        await event.answer(f"⚠️ 处理出错: {str(e)}")

    return
