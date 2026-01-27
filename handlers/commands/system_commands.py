from services.rule_service import RuleQueryService
from services.rule_management_service import rule_management_service
from services.system_service import system_service
from services.db_maintenance_service import db_maintenance_service
from services.forward_log_writer import forward_log_writer
from core.logging import get_logger
from core.helpers.auto_delete import async_delete_user_message, reply_and_delete

logger = get_logger(__name__)

async def handle_logs_command(event, parts):
    """处理 /logs 命令"""
    # 此处需要根据日志实现细节补充
    # 暂时占位
    await reply_and_delete(event, "Logs functionality pending migration.")

async def handle_download_logs_command(event, parts):
    await reply_and_delete(event, "Download Logs functionality pending migration.")

async def handle_db_optimize_command(event):
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("🧹 正在优化数据库...", parse_mode="md")
    
    result = await db_maintenance_service.optimize_database()
    
    if result['success']:
        await msg.edit(f"✅ **数据库优化完成**\n\n{result['message']}")
    else:
        await msg.edit(f"❌ **数据库优化失败**\n\n{result['error']}")

async def handle_db_info_command(event):
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("📊 正在获取数据库信息...", parse_mode="md")
    
    info = await db_maintenance_service.get_database_info()
    
    if info['success']:
        # 格式化输出
        text = f"**📦 数据库信息**\n\n"
        text += f"大小: `{info['size_mb']:.2f} MB`\n"
        text += f"总记录数: `{info['total_rows']}`\n\n"
        text += "**表详情:**\n"
        for table, count in info['tables'].items():
            text += f"- `{table}`: {count}\n"
            
        await msg.edit(text)
    else:
        await msg.edit(f"❌ 获取失败: {info.get('error')}")

async def handle_db_backup_command(event):
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("💾 正在备份数据库...", parse_mode="md")
    
    result = await db_maintenance_service.backup_database()
    
    if result['success']:
        await msg.edit(f"✅ **备份成功**\n\n路径: `{result['path']}`\n大小: `{result['size_mb']:.2f} MB`")
    else:
        await msg.edit(f"❌ **备份失败**\n\n{result['error']}")
    
async def handle_db_health_command(event):
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("🏥 正在检查数据库健康状态...", parse_mode="md")
    
    result = await db_maintenance_service.check_integrity()
    
    status_emoji = "✅" if result['integrity_check'] == 'ok' else "❌"
    
    text = f"**{status_emoji} 数据库健康报告**\n\n"
    text += f"完整性检查: `{result['integrity_check']}`\n"
    if 'fragmentation' in result:
         text += f"碎片率: `{result.get('fragmentation', 'N/A')}%`\n"
    
    await msg.edit(text)

async def handle_system_status_command(event):
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("🖥️ 正在获取系统状态...", parse_mode="md")
    
    status = await system_service.get_system_status()
    
    text = "**🖥️ 系统状态**\n\n"
    text += f"CPU: `{status['cpu_percent']}%`\n"
    text += f"内存: `{status['memory_percent']}%` (已用 {status['memory_used_mb']} MB)\n"
    text += f"磁盘: `{status['disk_percent']}%`\n"
    text += f"运行时间: `{status['uptime']}`\n"
    text += f"版本: `{status['version']}`\n"
    
    await msg.edit(text)
    
async def handle_video_cache_stats_command(event):
    await reply_and_delete(event, "Video cache stats not implemented in system commands yet.")

async def handle_video_cache_clear_command(event, parts):
    await reply_and_delete(event, "Video cache clear not implemented in system commands yet.")

async def handle_dedup_scan_command(event, parts):
    # This was already in command_handlers.py, so we can keep it there or move it to a dedup_commands.py.
    # For now, if command_handlers calls it locally, keep it there or import from here.
    # Given the previous context, handle_dedup_scan_command was defined in command_handlers.py.
    pass
    
async def handle_dedup_command(event):
    # Same as above.
    pass

async def handle_admin_panel_command(event):
    # This usually involves buttons, might be complex. Stub for now.
    await reply_and_delete(event, "Admin panel coming soon.")
