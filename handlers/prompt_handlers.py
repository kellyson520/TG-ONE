import traceback

import logging
from sqlalchemy import select

from core.container import container
from .button import button_helpers
from repositories.db_operations import DBOperations
from models.models import ForwardRule, PushConfig, ReplaceRule, RuleSync
from core.helpers.common import get_bot_client, get_main_module
from handlers.button.settings_manager import get_ai_settings_text
from core.helpers.auto_delete import (
    async_delete_user_message,
    send_message_and_delete,
)

from .advanced_media_prompt_handlers import handle_advanced_media_prompt
from services.session_service import session_manager

logger = logging.getLogger(__name__)


async def handle_prompt_setting(
    event, client, sender_id, chat_id, current_state, message
):
    """处理设置提示词的逻辑"""
    logger.info(
        f"开始处理提示词设置,用户ID:{sender_id},聊天ID:{chat_id},当前状态:{current_state}"
    )

    # 先尝试处理高级媒体筛选提示
    if await handle_advanced_media_prompt(event, sender_id, chat_id):
        return True

    if not current_state:
        logger.info("当前无状态,返回False")
        return False

    rule_id = None
    field_name = None
    prompt_type = None
    template_type = None

    if current_state.startswith("set_summary_prompt:"):
        rule_id = current_state.split(":")[1]
        field_name = "summary_prompt"
        prompt_type = "AI总结"
        template_type = "ai"
        logger.info(f"检测到设置总结提示词,规则ID:{rule_id}")
    elif current_state.startswith("set_ai_prompt:"):
        rule_id = current_state.split(":")[1]
        field_name = "ai_prompt"
        prompt_type = "AI"
        template_type = "ai"
        logger.info(f"检测到设置AI提示词,规则ID:{rule_id}")
    elif current_state.startswith("set_userinfo_template:"):
        rule_id = current_state.split(":")[1]
        field_name = "userinfo_template"
        prompt_type = "用户信息"
        template_type = "userinfo"
        logger.info(f"检测到设置用户信息模板,规则ID:{rule_id}")
    elif current_state.startswith("set_time_template:"):
        rule_id = current_state.split(":")[1]
        field_name = "time_template"
        prompt_type = "时间"
        template_type = "time"
        logger.info(f"检测到设置时间模板,规则ID:{rule_id}")
    elif current_state.startswith("set_original_link_template:"):
        rule_id = current_state.split(":")[1]
        field_name = "original_link_template"
        prompt_type = "原始链接"
        template_type = "link"
        logger.info(f"检测到设置原始链接模板,规则ID:{rule_id}")
    elif current_state.startswith("add_push_channel:"):
        # 处理添加推送频道
        rule_id = current_state.split(":")[1]
        logger.info(f"检测到添加推送频道,规则ID:{rule_id}")
        return await handle_add_push_channel(
            event, client, sender_id, chat_id, rule_id, message
        )
    elif current_state.startswith("kw_add:"):
        # 逐行添加关键词
        rule_id = int(current_state.split(":")[1])
        try:
            lines = [
                ln.strip()
                for ln in (event.message.text or "").splitlines()
                if ln.strip()
            ]
            if not lines:
                return True
            db_ops = await DBOperations.create()
            async with container.db.get_session() as session:
                await db_ops.add_keywords(
                    session, rule_id, lines, is_regex=False, is_blacklist=True
                )
            # 清除状态
            await send_message_and_delete(
                await get_bot_client(), chat_id, f"已添加 {len(lines)} 个关键词"
            )
            return True
        except Exception as e:
            logger.error(f"添加关键词失败: {e}")
            return True
    elif current_state.startswith("kw_delete:"):
        # 删除指定序号的关键词（空格/逗号分隔）
        rule_id = int(current_state.split(":")[1])
        try:
            import re

            nums = re.split(r"[\s,，]+", (event.message.text or "").strip())
            indices = []
            for n in nums:
                try:
                    if n:
                        indices.append(int(n))
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            if not indices:
                return True
            db_ops = await DBOperations.create()
            async with container.db.get_session() as session:
                deleted_count, _ = await db_ops.delete_keywords(
                    session, rule_id, indices
                )
            # 清除状态
            if sender_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[sender_id]:
                    del session_manager.user_sessions[sender_id][chat_id]
            await send_message_and_delete(
                await get_bot_client(), chat_id, f"已删除 {deleted_count} 个关键词"
            )
            return True
        except Exception as e:
            logger.error(f"删除关键词失败: {e}")
            return True
    elif current_state.startswith("rr_add:"):
        # 每行支持 "pattern => replacement" 或以空格分隔（replacement 可为空表示删除）
        rule_id = int(current_state.split(":")[1])
        try:
            rows = [
                ln.strip()
                for ln in (event.message.text or "").splitlines()
                if ln.strip()
            ]
            patterns = []
            contents = []
            for row in rows:
                if "=>" in row:
                    p, c = row.split("=>", 1)
                    patterns.append(p.strip())
                    contents.append(c.strip())
                else:
                    parts = row.split(None, 1)
                    p = parts[0]
                    c = parts[1] if len(parts) > 1 else ""
                    patterns.append(p)
                    contents.append(c)
            if not patterns:
                return True
            db_ops = await DBOperations.create()
            async with container.db.get_session() as session:
                await db_ops.add_replace_rules(session, rule_id, patterns, contents)
            # 清除状态
            if sender_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[sender_id]:
                    del session_manager.user_sessions[sender_id][chat_id]
            await send_message_and_delete(
                await get_bot_client(), chat_id, f"已添加 {len(patterns)} 条替换规则"
            )
            return True
        except Exception as e:
            logger.error(f"添加替换规则失败: {e}")
            return True
    elif current_state.startswith("rr_delete:"):
        # 删除替换规则按序号（空格/逗号分隔）
        rule_id = int(current_state.split(":")[1])
        try:
            import re

            nums = re.split(r"[\s,，]+", (event.message.text or "").strip())
            indices = []
            for n in nums:
                try:
                    if n:
                        indices.append(int(n))
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
            if not indices:
                return True
            # 将序号转为对应记录删除
            async with container.db.get_session() as session:
                result = await session.execute(
                    select(ReplaceRule).filter(ReplaceRule.rule_id == int(rule_id))
                )
                items = result.scalars().all()
                indices = sorted(set(i for i in indices if 1 <= i <= len(items)))
                for i in reversed(indices):
                    await session.delete(items[i - 1])
            # 清除状态
            if sender_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[sender_id]:
                    del session_manager.user_sessions[sender_id][chat_id]
            await send_message_and_delete(
                await get_bot_client(), chat_id, f"已删除 {len(indices)} 条替换规则"
            )
            return True
        except Exception as e:
            logger.error(f"删除替换规则失败: {e}")
            return True
    else:
        logger.info(f"未知的状态类型:{current_state}")
        return False

    logger.info(
        f"处理设置{prompt_type}提示词/模板,规则ID:{rule_id},字段名:{field_name}"
    )
    try:
        logger.info(f"查询规则ID:{rule_id}")
        async with container.db.get_session() as session:
            rule = await session.get(ForwardRule, int(rule_id))
            if rule:
                old_prompt = (
                    getattr(rule, field_name) if hasattr(rule, field_name) else None
                )
                new_prompt = event.message.text
                logger.info(f"找到规则,原提示词/模板:{old_prompt}")
                logger.info(f"准备更新为新提示词/模板:{new_prompt}")

                setattr(rule, field_name, new_prompt)
                logger.info(f"已更新规则{rule_id}的{prompt_type}提示词/模板")

                # 检查是否启用了同步功能
                if rule.enable_sync:
                    logger.info(
                        f"规则 {rule.id} 启用了同步功能，正在同步提示词/模板设置到关联规则"
                    )
                    # 获取需要同步的规则列表
                    result = await session.execute(
                        select(RuleSync).filter(RuleSync.rule_id == rule.id)
                    )
                    sync_rules = result.scalars().all()

                    # 为每个同步规则应用相同的提示词设置
                    for sync_rule in sync_rules:
                        sync_rule_id = sync_rule.sync_rule_id
                        logger.info(
                            f"正在同步{prompt_type}提示词/模板到规则 {sync_rule_id}"
                        )

                        # 获取同步目标规则
                        target_rule = await session.get(ForwardRule, sync_rule_id)
                        if not target_rule:
                            logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                            continue

                        # 更新同步目标规则的提示词设置
                        try:
                            # 记录旧提示词
                            old_target_prompt = (
                                getattr(target_rule, field_name)
                                if hasattr(target_rule, field_name)
                                else None
                            )

                            # 设置新提示词
                            setattr(target_rule, field_name, new_prompt)

                            logger.info(
                                f"同步规则 {sync_rule_id} 的{prompt_type}提示词/模板从 '{old_target_prompt}' 到 '{new_prompt}'"
                            )
                        except Exception as e:
                            logger.error(
                                f"同步{prompt_type}提示词/模板到规则 {sync_rule_id} 时出错: {str(e)}"
                            )
                            continue

                    logger.info("所有同步提示词/模板更改已提交")

            logger.info(f"清除用户状态,用户ID:{sender_id},聊天ID:{chat_id}")
            # 清除状态
            if sender_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[sender_id]:
                    del session_manager.user_sessions[sender_id][chat_id]

            message_chat_id = event.message.chat_id
            bot_client = await get_bot_client()

            try:
                await async_delete_user_message(
                    bot_client, message_chat_id, event.message.id, 0
                )
            except Exception as e:
                logger.error(f"删除用户消息失败: {str(e)}")

            await message.delete()
            logger.info("准备发送更新后的设置消息")

            # 根据模板类型选择不同的显示页面
            if template_type == "ai":
                # AI设置页面
                await client.send_message(
                    chat_id,
                    await get_ai_settings_text(rule),
                    buttons=await button_helpers.create_ai_settings_buttons(rule),
                )
            elif template_type in ["userinfo", "time", "link"]:
                # 其他设置页面
                await client.send_message(
                    chat_id,
                    f"已更新规则 {rule_id} 的{prompt_type}模板",
                    buttons=await button_helpers.create_other_settings_buttons(
                        rule_id=rule_id
                    ),
                )

            # 删除用户消息
            logger.info("设置消息发送成功")
            return True
    except Exception as e:
        logger.error(f"处理提示词/模板设置时发生错误:{str(e)}")
        raise
    return True


async def handle_add_push_channel(event, client, sender_id, chat_id, rule_id, message):
    """处理添加推送频道的逻辑"""
    logger.info(f"开始处理添加推送频道,规则ID:{rule_id}")

    try:
        # 获取规则
        async with container.db.get_session() as session:
            rule = await session.get(ForwardRule, int(rule_id))
            if not rule:
                logger.warning(f"未找到规则ID:{rule_id}")
                return False

            # 获取用户输入的推送频道信息
            push_channel = event.message.text.strip()
            logger.info(f"用户输入的推送频道: {push_channel}")

            # 创建新的推送配置
            is_email = push_channel.startswith(("mailto://", "mailtos://", "email://"))
            push_config = PushConfig(
                rule_id=int(rule_id),
                push_channel=push_channel,
                enable_push_channel=True,
                media_send_mode="Multiple" if is_email else "Single",
            )
            await session.add(push_config)

            # 启用规则的推送功能
            rule.enable_push = True

            # 检查是否启用了同步功能
            if rule.enable_sync:
                logger.info(
                    f"规则 {rule.id} 启用了同步功能，正在同步推送配置到关联规则"
                )

                # 获取需要同步的规则列表
                result = await session.execute(
                    select(RuleSync).filter(RuleSync.rule_id == rule.id)
                )
                sync_rules = result.scalars().all()

                # 为每个同步规则创建相同的推送配置
                for sync_rule in sync_rules:
                    sync_rule_id = sync_rule.sync_rule_id
                    logger.info(f"正在同步推送配置到规则 {sync_rule_id}")

                    # 获取同步目标规则
                    target_rule = await session.get(ForwardRule, sync_rule_id)
                    if not target_rule:
                        logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                        continue

                    # 检查目标规则是否已存在相同推送频道
                    result = await session.execute(
                        select(PushConfig)
                        .filter_by(rule_id=sync_rule_id, push_channel=push_channel)
                        .limit(1)
                    )
                    existing_config = result.scalar_one_or_none()

                    if existing_config:
                        logger.info(
                            f"目标规则 {sync_rule_id} 已存在推送频道 {push_channel}，跳过"
                        )
                        continue

                    # 创建新的推送配置
                    try:
                        sync_push_config = PushConfig(
                            rule_id=sync_rule_id,
                            push_channel=push_channel,
                            enable_push_channel=True,
                            media_send_mode=push_config.media_send_mode,
                        )
                        await session.add(sync_push_config)

                        # 启用目标规则的推送功能
                        target_rule.enable_push = True

                        logger.info(
                            f"已为规则 {sync_rule_id} 添加推送频道 {push_channel}"
                        )
                    except Exception as e:
                        logger.error(
                            f"为规则 {sync_rule_id} 添加推送配置时出错: {str(e)}"
                        )
                        continue

        # 清除状态
        if sender_id in session_manager.user_sessions:
            if chat_id in session_manager.user_sessions[sender_id]:
                del session_manager.user_sessions[sender_id][chat_id]

        # 删除用户消息
        message_chat_id = event.message.chat_id
        bot_client = await get_bot_client()
        try:
            await async_delete_user_message(
                bot_client, message_chat_id, event.message.id, 0
            )
        except Exception as e:
            logger.error(f"删除用户消息失败: {str(e)}")

        # 删除原始消息并显示结果
        await message.delete()

        # 获取主界面
        main_module = await get_main_module()
        bot_client = main_module.bot_client

        # 发送结果通知
        success = True
        message_text = "成功添加推送配置"
        if success:
            await send_message_and_delete(
                bot_client,
                chat_id,
                f"已成功添加推送频道: {push_channel}",
                buttons=await button_helpers.create_push_settings_buttons(rule_id),
            )
        else:
            await send_message_and_delete(
                bot_client,
                chat_id,
                f"添加推送频道失败: {message_text}",
                buttons=await button_helpers.create_push_settings_buttons(rule_id),
            )

        return True
    except Exception as e:
        logger.error(f"处理添加推送频道时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return False
