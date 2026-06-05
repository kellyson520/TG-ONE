import logging
from handlers.button.button_helpers import create_sync_rule_buttons
from core.container import container

logger = logging.getLogger(__name__)

async def callback_set_sync_rule(event, rule_id, session, message, data):
    """处理设置同步规则的回调"""
    try:
        rid = int(rule_id)
        # 验证规则是否存在 (通过 Repo)
        rule = await container.rule_repo.get_by_id(rid)
        if not rule:
            await event.answer("规则不存在")
            return
        
        await message.edit("请选择要同步到的规则：", buttons=await create_sync_rule_buttons(rule_id, page=0))
    except (ValueError, TypeError):
        await event.answer("无效的规则ID", alert=True)
    except Exception as e:
        logger.error(f"设置同步规则时出错: {str(e)}")
        await event.answer("⚠️ 无法加载列表")
    return

async def callback_toggle_rule_sync(event, rule_id_data, session, message, data):
    """处理切换规则同步状态的回调"""
    try:
        parts = rule_id_data.split(":")
        source_rule_id = int(parts[0])
        target_rule_id = int(parts[1])
        page = int(parts[2])

        # 使用 Service 层处理切换逻辑
        res = await container.rule_service.toggle_rule_sync(source_rule_id, target_rule_id)
        
        if res.get('success'):
            action_text = "已建立同步关系" if res.get('action') == "added" else "已取消同步关系"
            await event.answer(f"✅ {action_text}")
        else:
            await event.answer(f"❌ 操作失败: {res.get('error')}")

        await message.edit("请选择要同步到的规则：", buttons=await create_sync_rule_buttons(source_rule_id, page))

    except Exception as e:
        logger.error(f"切换规则同步状态时出错: {str(e)}")
        await event.answer("⚠️ 操作失败")
    return

async def callback_sync_rule_page(event, rule_id_data, session, message, data):
    """处理同步规则页面的翻页功能"""
    try:
        parts = rule_id_data.split(":")
        rule_id = int(parts[0])
        page = int(parts[1])
        
        # 验证
        rule = await container.rule_repo.get_by_id(rule_id)
        if not rule:
            await event.answer("规则不存在")
            return
            
        await message.edit("请选择要同步到的规则：", buttons=await create_sync_rule_buttons(rule_id, page))
    except Exception as e:
        logger.error(f"处理同步规则页面翻页时出错: {str(e)}")
    return
