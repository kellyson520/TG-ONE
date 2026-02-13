import logging
from telethon import Button
from core.container import container
from handlers.button.settings_manager import create_buttons, create_settings_text, get_ai_settings_text, create_ai_settings_buttons
from handlers.button.button_helpers import create_delay_time_buttons, create_other_settings_buttons, create_media_settings_buttons, create_push_settings_buttons
from ui.constants import PUSH_SETTINGS_TEXT

logger = logging.getLogger(__name__)

async def callback_settings(event, rule_id, session, message, data):
    """处理显示设置的回调"""
    try:
        current_chat = await event.get_chat()
        
        # 使用 Repository 层的 DTO 查找
        current_chat_dto = await container.rule_repo.find_chat(current_chat.id)
        
        if not current_chat_dto:
            await event.answer("当前聊天未收录，请先使用 /bind 绑定")
            return

        # 使用 QueryService 获取规则列表
        rules_list = await container.rule_query_service.get_rules_for_target_chat(current_chat_dto.id)

        if not rules_list:
            await event.answer("当前聊天没有任何转发规则")
            return

        buttons = []
        for rule in rules_list:
            source_name = rule.source_chat.name if rule.source_chat else "未知来源"
            button_text = f"{source_name}"
            callback_data = f"rule_settings:{rule.id}"
            buttons.append([Button.inline(button_text, callback_data)])

        await message.edit("请选择要管理的转发规则:", buttons=buttons)
    except Exception as e:
        logger.error(f"处理显示设置回调失败: {e}", exc_info=True)
        await event.answer(f"⚠️ 处理失败: {str(e)}")

async def callback_rule_settings(event, rule_id, session, message, data):
    """处理规则设置的回调"""
    try:
        # 使用 Repository 层的 DTO 获取详情
        rule = await container.rule_repo.get_by_id(int(rule_id))
        
        if not rule:
            await event.answer("规则不存在")
            return
        
        await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
    except Exception as e:
        logger.error(f"处理规则设置回调失败: {e}", exc_info=True)
        await event.answer(f"⚠️ 无法加载设置: {str(e)}")

async def callback_set_delay_time(event, rule_id, session, message, data):
    await event.edit(
        "请选择延迟时间：", buttons=await create_delay_time_buttons(rule_id, page=0)
    )
    return

async def callback_delay_time_page(event, rule_id, session, message, data):
    _, rule_id, page = data.split(":")
    page = int(page)
    await event.edit(
        "请选择延迟时间：", buttons=await create_delay_time_buttons(rule_id, page=page)
    )
    return

async def callback_select_delay_time(event, rule_id, session, message, data):
    parts = data.split(":", 2)
    if len(parts) == 3:
        _, rule_id, time = parts
        logger.info(f"设置规则 {rule_id} 的延迟时间为: {time}")
        try:
            # 使用 Service 层更新
            res = await container.rule_service.update_rule(int(rule_id), delay_seconds=int(time))
            
            if res.get('success'):
                # 获取最新 DTO 刷新界面
                rule = await container.rule_repo.get_by_id(int(rule_id))
                msg_obj = await event.get_message()
                await msg_obj.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
            else:
                await event.answer(f"❌ 设置失败: {res.get('error')}")
        except Exception as e:
            logger.error(f"设置延迟时间时出错: {str(e)}")
            await event.answer("⚠️ 设置失败")
    return

async def update_rule_setting(
    event, rule_id, message, field_name, config, setting_type, session=None
):
    """通用的规则设置更新函数"""
    logger.info(f"找到匹配的设置项: {field_name}")

    try:
        # 使用 Service 层的统一切换逻辑 (自动处理同步、提交、缓存失效)
        res = await container.rule_service.toggle_rule_setting(int(rule_id), field_name)
        
        if not res.get('success'):
            await event.answer(f"❌ 更新失败: {res.get('error')}")
            return False

        # 获取最新 DTO 刷新 UI
        rule = await container.rule_repo.get_by_id(int(rule_id))
        
        # 刷新 UI
        if setting_type == "rule":
             await message.edit(await create_settings_text(rule), buttons=await create_buttons(rule))
        elif setting_type == "media":
             await event.edit("媒体设置：", buttons=await create_media_settings_buttons(rule))
        elif setting_type == "ai":
             await message.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
        elif setting_type == "other":
             await event.edit("其他设置：", buttons=await create_other_settings_buttons(rule))
        elif setting_type == "push":
             await event.edit(PUSH_SETTINGS_TEXT, buttons=await create_push_settings_buttons(rule), link_preview=False)

        await event.answer(f"已更新 {config.get('display_name', field_name)}")
        return True
    except Exception as e:
        logger.error(f"更新规则设置失败: {e}", exc_info=True)
        await event.answer("⚠️ 更新失败")
        return False
