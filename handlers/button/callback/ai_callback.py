import traceback

import asyncio
import logging
from core.config import settings
from sqlalchemy import select
from telethon import Button
from telethon.tl import types

from services.session_service import session_manager
from core.container import container
from models.models import ForwardRule, RuleSync
from scheduler.summary_scheduler import SummaryScheduler
from core.helpers.common import get_main_module, is_admin
from handlers.button.settings_manager import get_ai_settings_text

from handlers.button.button_helpers import (
    create_ai_settings_buttons,
    create_model_buttons,
    create_summary_time_buttons,
)

logger = logging.getLogger(__name__)


async def handle_ai_callback(event, **kwargs):
    """处理AI设置相关回调 (异步版)"""
    data = event.data.decode("utf-8")
    parts = data.split(":")
    action = parts[0]

    # 解析 rule_id
    rule_id = None
    if ":" in data:
        rule_id = parts[1]

    # 使用 AsyncSessionManager 获取会话
    async with container.db.session() as session:
        message = await event.get_message()
        # 获取对应的处理器
        handler = {
            "ai_settings": callback_ai_settings,
            "set_summary_time": callback_set_summary_time,
            "set_summary_prompt": callback_set_summary_prompt,
            "set_ai_prompt": callback_set_ai_prompt,
            "time_page": callback_time_page,
            "select_time": callback_select_time,
            "select_model": callback_select_model,
            "model_page": callback_model_page,
            "change_model": callback_change_model,
            "cancel_set_prompt": callback_cancel_set_prompt,
            "cancel_set_summary": callback_cancel_set_summary,
            "summary_now": callback_summary_now,
        }.get(action)

        if handler:
            await handler(event, rule_id, session, message, data)


async def callback_ai_settings(event, rule_id, session, message, data):
    # 显示 AI 设置页面
    rule = await session.get(ForwardRule, int(rule_id))
    if rule:
        await event.edit(
            await get_ai_settings_text(rule),
            buttons=await create_ai_settings_buttons(rule),
        )
    return


async def callback_set_summary_time(event, rule_id, session, message, data):
    await event.edit(
        "请选择总结时间：", buttons=await create_summary_time_buttons(rule_id, page=0)
    )
    return


async def callback_set_summary_prompt(event, rule_id, session, message, data):
    """处理设置AI总结提示词的回调"""
    logger.info(f"开始处理设置AI总结提示词回调 - event: {event}, rule_id: {rule_id}")

    rule = await session.get(ForwardRule, rule_id)
    if not rule:
        await event.answer("规则不存在")
        return

    user_id = event.sender_id
    chat_id = event.chat_id
    state = f"set_summary_prompt:{rule_id}"

    logger.info(
        f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}"
    )
    try:
        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "ai",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_prompt = rule.summary_prompt or settings.DEFAULT_SUMMARY_PROMPT
        await message.edit(
            f"请发送新的AI总结提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前AI总结提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_summary:{rule_id}")]],
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)


async def cancel_state_after_timeout(
    user_id: int, chat_id: int, timeout_minutes: int = 5
):
    """在指定时间后自动取消状态"""
    await asyncio.sleep(timeout_minutes * 60)
    # 使用 session_manager 替代 state_manager
    user_session = session_manager.user_sessions.get(user_id, {})
    chat_state = user_session.get(chat_id, {})
    current_state = chat_state.get("state")
    if current_state:  # 只有当状态还存在时才清除
        logger.info(f"状态超时自动取消 - user_id: {user_id}, chat_id: {chat_id}")
        user_session.pop(chat_id)
        # 如果用户会话为空，清理掉该用户的会话记录
        if not user_session:
            session_manager.user_sessions.pop(user_id)


async def callback_set_ai_prompt(event, rule_id, session, message, data):
    """处理设置AI提示词的回调"""
    logger.info(f"开始处理设置AI提示词回调 - event: {event}, rule_id: {rule_id}")

    rule = await session.get(ForwardRule, rule_id)
    if not rule:
        await event.answer("规则不存在")
        return

    user_id = event.sender_id
    chat_id = event.chat_id
    state = f"set_ai_prompt:{rule_id}"

    logger.info(
        f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}"
    )
    try:
        # 使用 session_manager 替代 state_manager
        if user_id not in session_manager.user_sessions:
            session_manager.user_sessions[user_id] = {}
        session_manager.user_sessions[user_id][chat_id] = {
            "state": state,
            "message": message,
            "state_type": "ai",
        }
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_prompt = rule.ai_prompt or settings.DEFAULT_AI_PROMPT
        await message.edit(
            f"请发送新的AI提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前AI提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_prompt:{rule_id}")]],
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)


async def callback_time_page(event, rule_id, session, message, data):
    _, rule_id, page = data.split(":")
    page = int(page)
    await event.edit(
        "请选择总结时间：",
        buttons=await create_summary_time_buttons(rule_id, page=page),
    )
    return


async def callback_select_time(event, rule_id, session, message, data):
    parts = data.split(":", 2)  # 最多分割2次
    if len(parts) == 3:
        _, rule_id, time = parts
        logger.info(f"设置规则 {rule_id} 的总结时间为: {time}")
        try:
            rule = await session.get(ForwardRule, int(rule_id))
            if rule:
                # 记录旧时间
                old_time = rule.summary_time

                # 更新时间
                rule.summary_time = time
                await session.commit()
                logger.info(f"数据库更新成功: {old_time} -> {time}")

                # 检查是否启用了同步功能
                if rule.enable_sync:
                    logger.info(
                        f"规则 {rule.id} 启用了同步功能，正在同步总结时间设置到关联规则"
                    )
                    # 获取需要同步的规则列表
                    result = await session.execute(
                        select(RuleSync).filter(RuleSync.rule_id == rule.id)
                    )
                    sync_rules = result.scalars().all()

                    # 为每个同步规则应用相同的总结时间设置
                    for sync_rule in sync_rules:
                        sync_rule_id = sync_rule.sync_rule_id
                        logger.info(f"正在同步总结时间到规则 {sync_rule_id}")

                        # 获取同步目标规则
                        target_rule = await session.get(ForwardRule, sync_rule_id)
                        if not target_rule:
                            logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                            continue

                        # 更新同步目标规则的总结时间设置
                        try:
                            # 记录旧时间
                            old_target_time = target_rule.summary_time

                            # 设置新时间
                            target_rule.summary_time = time

                            # 如果目标规则启用了总结功能，也更新它的调度
                            if target_rule.is_summary:
                                logger.info(
                                    f"目标规则 {sync_rule_id} 启用了总结功能，更新其调度任务"
                                )
                                main = await get_main_module()
                                if hasattr(main, "scheduler") and main.scheduler:
                                    await main.scheduler.schedule_rule(target_rule)
                                    logger.info(
                                        f"目标规则调度任务更新成功，新时间: {time}"
                                    )
                                else:
                                    logger.warning("调度器未初始化")

                            logger.info(
                                f"同步规则 {sync_rule_id} 的总结时间从 {old_target_time} 到 {time}"
                            )
                        except Exception as e:
                            logger.error(
                                f"同步总结时间到规则 {sync_rule_id} 时出错: {str(e)}"
                            )
                            continue

                    # 提交所有同步更改
                    await session.commit()
                    logger.info("所有同步总结时间更改已提交")

                # 如果总结功能已开启，重新调度任务
                if rule.is_summary:
                    logger.info("规则已启用总结功能，开始更新调度任务")
                    main = await get_main_module()
                    if hasattr(main, "scheduler") and main.scheduler:
                        await main.scheduler.schedule_rule(rule)
                        logger.info(f"调度任务更新成功，新时间: {time}")
                    else:
                        logger.warning("调度器未初始化")
                else:
                    logger.info("规则未启用总结功能，跳过调度任务更新")

                await event.edit(
                    await get_ai_settings_text(rule),
                    buttons=await create_ai_settings_buttons(rule),
                )
                logger.info("界面更新完成")
        except Exception as e:
            logger.error(f"设置总结时间时出错: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
    return


async def callback_select_model(event, rule_id, session, message, data):
    # 分割数据，最多分割2次，将第三部分直接作为完整的模型名称
    parts = data.split(":", 2)
    _, rule_id_part, model = parts

    rule = await session.get(ForwardRule, int(rule_id_part))
    if rule:
        # 记录旧模型
        old_model = rule.ai_model

        # 更新模型
        rule.ai_model = model
        await session.commit()
        logger.info(f"已更新规则 {rule_id_part} 的AI模型为: {model}")

        # 检查是否启用了同步功能
        if rule.enable_sync:
            logger.info(
                f"规则 {rule.id} 启用了同步功能，正在同步AI模型设置到关联规则"
            )
            # 获取需要同步的规则列表
            result = await session.execute(
                select(RuleSync).filter(RuleSync.rule_id == rule.id)
            )
            sync_rules = result.scalars().all()

            # 为每个同步规则应用相同的AI模型设置
            for sync_rule in sync_rules:
                sync_rule_id = sync_rule.sync_rule_id
                logger.info(f"正在同步AI模型到规则 {sync_rule_id}")

                # 获取同步目标规则
                target_rule = await session.get(ForwardRule, sync_rule_id)
                if not target_rule:
                    logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                    continue

                # 更新同步目标规则的AI模型设置
                try:
                    # 记录旧模型
                    old_target_model = target_rule.ai_model

                    # 设置新模型
                    target_rule.ai_model = model

                    logger.info(
                        f"同步规则 {sync_rule_id} 的AI模型从 {old_target_model} 到 {model}"
                    )
                except Exception as e:
                    logger.error(
                        f"同步AI模型到规则 {sync_rule_id} 时出错: {str(e)}"
                    )
                    continue

            # 提交所有同步更改
            await session.commit()
            logger.info("所有同步AI模型更改已提交")

            await event.edit(
                await get_ai_settings_text(rule),
                buttons=await create_ai_settings_buttons(rule),
            )
    return


async def callback_model_page(event, rule_id, session, message, data):
    # 处理翻页
    _, rule_id, page = data.split(":")
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
    rule_id = data.split(":")[1]
    rule = await session.get(ForwardRule, int(rule_id))
    if rule:
        # 清除状态
        # 使用 session_manager 替代 state_manager
        user_id = event.sender_id
        chat_id = event.chat_id
        if user_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[user_id]:
                session_manager.user_sessions[user_id].pop(chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not session_manager.user_sessions[user_id]:
                    session_manager.user_sessions.pop(user_id)
        # 返回到 AI 设置页面
        await event.edit(
            await get_ai_settings_text(rule),
            buttons=await create_ai_settings_buttons(rule),
        )
        await event.answer("已取消设置")
    return


async def callback_cancel_set_summary(event, rule_id, session, message, data):
    # 处理取消设置总结
    rule_id = data.split(":")[1]
    rule = await session.get(ForwardRule, int(rule_id))
    if rule:
        # 清除状态
        # 使用 session_manager 替代 state_manager
        user_id = event.sender_id
        chat_id = event.chat_id
        if user_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[user_id]:
                session_manager.user_sessions[user_id].pop(chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not session_manager.user_sessions[user_id]:
                    session_manager.user_sessions.pop(user_id)
        # 返回到 AI 设置页面
        await event.edit(
            await get_ai_settings_text(rule),
            buttons=await create_ai_settings_buttons(rule),
        )
        await event.answer("已取消设置")
    return


async def callback_summary_now(event, rule_id, session, message, data):
    # 处理立即执行总结的回调
    logger.info(f"处理立即执行总结回调 - rule_id: {rule_id}")

    try:
        rule = await session.get(ForwardRule, int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return

        main = await get_main_module()
        user_client = main.user_client
        bot_client = main.bot_client

        scheduler = SummaryScheduler(user_client, bot_client)
        await event.answer("开始执行总结，请稍候...")

        await message.edit(
            f"正在为规则 {rule_id}（{rule.source_chat.name} -> {rule.target_chat.name}）生成总结...\n"
            f"处理需要一定时间，请耐心等待。",
            buttons=[[Button.inline("返回", f"ai_settings:{rule_id}")]],
        )

        try:
            # 执行总结任务
            await asyncio.create_task(scheduler._execute_summary(rule.id, is_now=True))
            logger.info(f"已启动规则 {rule_id} 的立即总结任务")
        except Exception as e:
            logger.error(f"执行总结任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            await message.edit(
                f"总结生成失败: {str(e)}",
                buttons=[[Button.inline("返回", f"ai_settings:{rule_id}")]],
            )
    except Exception as e:
        logger.error(f"处理总结时出错: {str(e)}")
        logger.error(traceback.format_exc())
        await event.answer(f"处理时出错: {str(e)}")

    return
