import traceback
import logging

from core.container import container
from .button import button_helpers
from core.helpers.common import get_bot_client
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

    if await handle_advanced_media_prompt(event, sender_id, chat_id):
        return True

    if not current_state:
        logger.info("当前无状态,返回False")
        return False

    if current_state == "set_history_limit":
        return await _handle_history_limit(event, sender_id, chat_id)

    if current_state.startswith("add_push_channel:"):
        rule_id = current_state.split(":")[1]
        logger.info(f"检测到添加推送频道,规则ID:{rule_id}")
        return await handle_add_push_channel(
            event, client, sender_id, chat_id, rule_id, message
        )

    _state_handlers = {
        "kw_add:": _handle_keyword_add,
        "kw_delete:": _handle_keyword_delete,
        "rr_add:": _handle_replace_rule_add,
        "rr_delete:": _handle_replace_rule_delete,
        "set_val:": _handle_set_val,
    }
    for prefix, handler in _state_handlers.items():
        if current_state.startswith(prefix):
            return await handler(event, sender_id, chat_id, current_state, message)

    if current_state == "hotword_add_noise":
        return await _handle_hotword_noise(event, client, sender_id, chat_id, message)

    _template_states = {
        "set_summary_prompt:": ("summary_prompt", "AI总结", "ai"),
        "set_ai_prompt:": ("ai_prompt", "AI", "ai"),
        "set_userinfo_template:": ("userinfo_template", "用户信息", "userinfo"),
        "set_time_template:": ("time_template", "时间", "time"),
        "set_original_link_template:": ("original_link_template", "原始链接", "link"),
    }
    for prefix, (field_name, prompt_type, template_type) in _template_states.items():
        if current_state.startswith(prefix):
            rule_id = current_state.split(":")[1]
            logger.info(f"检测到设置{prompt_type},规则ID:{rule_id}")
            return await _handle_prompt_template_update(
                event, client, sender_id, chat_id, message,
                rule_id, field_name, prompt_type, template_type,
            )

    logger.info(f"未知的状态类型:{current_state}")
    return False


def _clear_user_state(sender_id, chat_id):
    """清除用户的会话状态"""
    if sender_id in session_manager.user_sessions:
        if chat_id in session_manager.user_sessions[sender_id]:
            del session_manager.user_sessions[sender_id][chat_id]


async def _handle_history_limit(event, sender_id, chat_id):
    """处理历史消息数量限制设置"""
    raw_value = (event.message.text or "").strip().replace(",", "")
    res = await session_manager.set_history_message_limit(raw_value)
    if res.get("success"):
        if sender_id in session_manager.user_sessions:
            session_manager.user_sessions[sender_id].pop(chat_id, None)
            if not session_manager.user_sessions[sender_id]:
                session_manager.user_sessions.pop(sender_id, None)
        limit = res.get("limit", 0)
        label = f"{limit:,} 条" if limit > 0 else "无限制"
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"✅ 历史消息数量限制已设置为 {label}"
        )
    else:
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"❌ {res.get('error', '设置失败')}"
        )
    return True


async def _handle_keyword_add(event, sender_id, chat_id, current_state, message):
    """逐行添加关键词"""
    rule_id = int(current_state.split(":")[1])
    try:
        lines = [
            ln.strip()
            for ln in (event.message.text or "").splitlines()
            if ln.strip()
        ]
        if not lines:
            return True
        await container.rule_service.add_keywords(
            rule_id, lines, is_regex=False, is_negative=True
        )
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"已添加 {len(lines)} 个关键词"
        )
        return True
    except Exception as e:
        logger.error(f"添加关键词失败: {e}")
        return True


async def _handle_keyword_delete(event, sender_id, chat_id, current_state, message):
    """删除指定序号的关键词"""
    import re
    rule_id = int(current_state.split(":")[1])
    try:
        nums = re.split(r"[\s,，]+", (event.message.text or "").strip())
        indices = [int(n) for n in nums if n]
        if not indices:
            return True
        res = await container.rule_service.delete_keywords_by_indices(rule_id, indices)
        deleted_count = res.get('deleted', 0)
        _clear_user_state(sender_id, chat_id)
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"已删除 {deleted_count} 个关键词"
        )
        return True
    except Exception as e:
        logger.error(f"删除关键词失败: {e}")
        return True


async def _handle_replace_rule_add(event, sender_id, chat_id, current_state, message):
    """添加替换规则，每行支持 'pattern => replacement' 或空格分隔"""
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
        _clear_user_state(sender_id, chat_id)
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"已添加 {len(patterns)} 条替换规则"
        )
        return True
    except Exception as e:
        logger.error(f"添加替换规则失败: {e}")
        return True


async def _handle_replace_rule_delete(event, sender_id, chat_id, current_state, message):
    """按序号删除替换规则"""
    import re
    rule_id = int(current_state.split(":")[1])
    try:
        nums = re.split(r"[\s,，]+", (event.message.text or "").strip())
        indices = [int(n) for n in nums if n]
        if not indices:
            return True
        await container.rule_service.delete_replace_rules_by_indices(rule_id, indices)
        _clear_user_state(sender_id, chat_id)
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"已删除 {len(indices)} 条替换规则"
        )
        return True
    except Exception as e:
        logger.error(f"删除替换规则失败: {e}")
        return True


async def _handle_set_val(event, sender_id, chat_id, current_state, message):
    """通用设置项更新: set_val:rule_id:key"""
    parts = current_state.split(":")
    rule_id = int(parts[1])
    key = parts[2]
    new_val = (event.message.text or "").strip()

    if new_val == "取消":
        _clear_user_state(sender_id, chat_id)
        await message.delete()
        from controllers.menu_controller import menu_controller
        await menu_controller.show_rule_detail(event, rule_id)
        return True

    try:
        final_val = new_val
        if key in ['max_media_size', 'delay_seconds']:
            final_val = int(new_val)
        res = await container.rule_service.toggle_rule_setting(rule_id, key, final_val)
        if not res.get('success'):
            await event.reply(f"❌ 更新失败: {res.get('error', '未知错误')}")
            return True
        _clear_user_state(sender_id, chat_id)
        await message.delete()
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"✅ 已成功更新 `{key}` 为 `{new_val}`"
        )
        from controllers.menu_controller import menu_controller
        media_keys = ['max_media_size', 'enable_duration_filter', 'enable_resolution_filter', 'enable_file_size_range']
        ai_keys = ['ai_model', 'ai_prompt', 'ai_persona', 'is_ai', 'is_summary', 'summary_time', 'summary_prompt']
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


async def _handle_hotword_noise(event, client, sender_id, chat_id, message):
    """逐行添加热词垃圾库"""
    try:
        lines = [ln.strip() for ln in (event.message.text or "").splitlines() if ln.strip()]
        if not lines:
            return True
        from services.hotword_service import get_hotword_service
        from ui.renderers.hotword_renderer import hotword_renderer
        hotword_service = get_hotword_service()
        for ln in lines:
            await hotword_service.add_noise_word(ln)
        _clear_user_state(sender_id, chat_id)
        await message.delete()
        await send_message_and_delete(
            await get_bot_client(), chat_id, f"✅ 已添加 {len(lines)} 个词汇到垃圾库"
        )
        data = await hotword_service.get_noise_list(page=1)
        result = hotword_renderer.render_noise_list(data)
        await client.send_message(chat_id, result.text, buttons=result.buttons)
        return True
    except Exception as e:
        logger.error(f"添加热词垃圾失败: {e}")
        return True


async def _handle_prompt_template_update(
    event, client, sender_id, chat_id, message,
    rule_id, field_name, prompt_type, template_type,
):
    """处理提示词/模板的更新"""
    logger.info(f"处理设置{prompt_type}提示词/模板,规则ID:{rule_id},字段名:{field_name}")
    try:
        new_prompt = event.message.text
        res = await container.rule_service.toggle_rule_setting(int(rule_id), field_name, new_prompt)
        if not res.get('success'):
            logger.error(f"更新提示词失败: {res.get('error')}")
            await event.reply(f"❌ 更新失败: {res.get('error')}")
            return True
        _clear_user_state(sender_id, chat_id)
        message_chat_id = event.message.chat_id
        bot_client = await get_bot_client()
        try:
            await async_delete_user_message(
                bot_client, message_chat_id, event.message.id, 0
            )
        except Exception as e:
            logger.error(f"删除用户消息失败: {str(e)}")
        await message.delete()
        rule = await container.rule_repo.get_by_id(int(rule_id))
        if template_type == "ai":
            await client.send_message(
                chat_id,
                await get_ai_settings_text(rule),
                buttons=await button_helpers.create_ai_settings_buttons(rule),
            )
        elif template_type in ["userinfo", "time", "link"]:
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


async def handle_add_push_channel(event, client, sender_id, chat_id, rule_id, message):
    """处理添加推送频道的逻辑"""
    logger.info(f"开始处理添加推送频道,规则ID:{rule_id}")

    try:
        push_channel = event.message.text.strip()
        logger.info(f"用户输入的推送频道: {push_channel}")

        res = await container.rule_service.add_push_config(int(rule_id), push_channel)

        if not res.get('success'):
             await event.reply(f"❌ 添加推送配置失败: {res.get('error')}")
             return True

        _clear_user_state(sender_id, chat_id)

        message_chat_id = event.message.chat_id
        bot_client = await get_bot_client()
        try:
            await async_delete_user_message(
                bot_client, message_chat_id, event.message.id, 0
            )
        except Exception as e:
            logger.error(f"删除用户消息失败: {str(e)}")

        await message.delete()

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
