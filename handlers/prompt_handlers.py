import traceback
import logging

from core.container import container
from .button import button_helpers
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
            
            # 使用 Service 层替换直接仓库调用
            await container.rule_service.add_keywords(
                rule_id, lines, is_regex=False, is_negative=True
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
            # 解析出来的序号用于删除
            indices = []
            for n in nums:
                try:
                    if n:
                        indices.append(int(n))
                except Exception:
                    continue
                    
            if not indices:
                return True
            
            # 使用 Service 层替换直接 DBOperations 调用
            res = await container.rule_service.delete_keywords_by_indices(rule_id, indices)
            deleted_count = res.get('deleted', 0)
            
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
        # 每行支持 "pattern => replacement" 或以空格分隔
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
            
            await container.rule_service.add_replace_rules(rule_id, patterns, contents)
            
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
        # 删除替换规则按序号
        rule_id = int(current_state.split(":")[1])
        try:
            import re

            nums = re.split(r"[\s,，]+", (event.message.text or "").strip())
            indices = []
            for n in nums:
                try:
                    if n:
                        indices.append(int(n))
                except Exception:
                    continue
                    
            if not indices:
                return True
            
            # 使用新增加的 Service 方法按索引删除
            await container.rule_service.delete_replace_rules_by_indices(rule_id, indices)
            
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
    elif current_state.startswith("set_val:"):
        # 通用设置项更新: set_val:rule_id:key
        parts = current_state.split(":")
        rule_id = int(parts[1])
        key = parts[2]
        new_val = (event.message.text or "").strip()
        
        if new_val == "取消":
            # 清除状态
            if sender_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[sender_id]:
                    del session_manager.user_sessions[sender_id][chat_id]
            await message.delete()
            # 返回详情页
            from controllers.menu_controller import menu_controller
            await menu_controller.show_rule_detail(event, rule_id)
            return True
            
        try:
            # 数据类型转换与校验
            final_val = new_val
            if key in ['max_media_size', 'delay_seconds']:
                final_val = int(new_val)
                
            # 使用 Service 层统一更新
            from core.container import container
            res = await container.rule_service.toggle_rule_setting(rule_id, key, final_val)
            
            if not res.get('success'):
                await event.reply(f"❌ 更新失败: {res.get('error', '未知错误')}")
                return True
                
            # 清除状态
            if sender_id in session_manager.user_sessions:
                if chat_id in session_manager.user_sessions[sender_id]:
                    del session_manager.user_sessions[sender_id][chat_id]
            
            await message.delete()
            await send_message_and_delete(await get_bot_client(), chat_id, f"✅ 已成功更新 `{key}` 为 `{new_val}`")
            
            # 智能回位：根据 key 返回对应的设置页面
            from controllers.menu_controller import menu_controller
            media_keys = ['max_media_size', 'enable_duration_filter', 'enable_resolution_filter', 'enable_file_size_range']
            ai_keys = ['ai_model', 'ai_prompt', 'is_ai', 'is_summary', 'summary_time', 'summary_prompt']
            
            if key in media_keys:
                await menu_controller.show_media_settings(event, rule_id)
            elif key in ai_keys:
                await menu_controller.show_ai_settings(event, rule_id)
            else:
                await menu_controller.show_rule_detail(event, rule_id)
                
            return True
        except ValueError:
            await event.reply("❌ 输入格式错误，请输入有效的数值。")
            return True
        except Exception as e:
            logger.error(f"通用更新失败: {e}")
            await event.reply(f"❌ 系统错误: {str(e)}")
            return True
    else:
        logger.info(f"未知的状态类型:{current_state}")
        return False

    logger.info(
        f"处理设置{prompt_type}提示词/模板,规则ID:{rule_id},字段名:{field_name}"
    )
    try:
        new_prompt = event.message.text
        # 使用 Service 层的统一设置方法，自动处理同步
        res = await container.rule_service.toggle_rule_setting(int(rule_id), field_name, new_prompt)
        
        if not res.get('success'):
            logger.error(f"更新提示词失败: {res.get('error')}")
            await event.reply(f"❌ 更新失败: {res.get('error')}")
            return True

        # 清除用户状态
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
        
        # 获取最新的规则详情用于显示
        rule = await container.rule_repo.get_by_id(int(rule_id))

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

        return True
    except Exception as e:
        logger.error(f"处理提示词/模板设置时发生错误:{str(e)}")
        raise
    return True


async def handle_add_push_channel(event, client, sender_id, chat_id, rule_id, message):
    """处理添加推送频道的逻辑"""
    logger.info(f"开始处理添加推送频道,规则ID:{rule_id}")

    try:
        # 获取用户输入的推送频道信息
        push_channel = event.message.text.strip()
        logger.info(f"用户输入的推送频道: {push_channel}")

        # 使用 Service 层处理添加和同步逻辑
        res = await container.rule_service.add_push_config(int(rule_id), push_channel)
        
        if not res.get('success'):
             await event.reply(f"❌ 添加推送配置失败: {res.get('error')}")
             return True

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

        # 发送结果通知
        await send_message_and_delete(
            bot_client,
            chat_id,
            f"已成功添加推送频道: {push_channel}",
            buttons=await button_helpers.create_push_settings_buttons(rule_id),
        )

        return True
    except Exception as e:
        logger.error(f"处理添加推送频道时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return False
