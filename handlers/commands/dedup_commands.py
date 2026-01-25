from services.rule_service import RuleQueryService
from services.rule_management_service import rule_management_service
from utils.processing.auto_delete import async_delete_user_message, reply_and_delete

async def handle_dedup_enable_command(event, parts):
    """开启/关闭去重 - 使用 RuleManagementService"""
    from core.container import container
    async with container.db.session() as session:
        rule_info = await RuleQueryService.get_current_rule_for_chat(event, session)
        if not rule_info:
            await reply_and_delete(event, "❌ 未找到管理上下文，请先 /switch 切换到目标聊天")
            return
        rule, source_chat = rule_info
        
        current_val = getattr(rule, "enable_dedup", False)
        new_val = not current_val
    
    # 使用 Service 层更新去重设置
    result = await rule_management_service.update_rule(
        rule_id=rule.id,
        enable_dedup=new_val
    )
    
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    if result.get('success'):
        status = "开启" if new_val else "关闭"
        tip = "将自动跳过已存在的相同媒体" if new_val else "不再检查重复"
        await reply_and_delete(event, f"✅ 已{status}去重\n{tip}")
    else:
        await reply_and_delete(event, f"❌ 切换去重失败: {result.get('error')}")

# Include handler for dedup scan command as well if not already in system or another place
async def handle_dedup_scan_command(event, parts):
    # This was already defined or imported, providing a clean place for it
    from handlers.commands.system_commands import handle_dedup_scan_command as sys_scan
    await sys_scan(event, parts)

async def handle_dedup_command(event):
    await handle_dedup_enable_command(event, None)
