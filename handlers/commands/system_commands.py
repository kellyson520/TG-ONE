import asyncio
from services.system_service import system_service
from services.update_service import update_service
from services.db_maintenance_service import db_maintenance_service
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
    
    # 异步检查更新并追加到状态中
    try:
        has_update, remote_ver = await update_service.check_for_updates(force=True)
        if has_update:
            text += f"\n🆕 **检测到新版本**: `{remote_ver}`\n使用 `/update` 进行更新。"
    except Exception as e:
        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
    
    await msg.edit(text)
    
async def handle_video_cache_stats_command(event):
    await reply_and_delete(event, "Video cache stats not implemented in system commands yet.")

async def handle_video_cache_clear_command(event, parts):
    await reply_and_delete(event, "Video cache clear not implemented in system commands yet.")

async def handle_dedup_scan_command(event, parts):
    """手动触发去重扫描"""
    from services.session_service import session_manager
    msg = await event.respond("⏳ 正在扫描重复消息...", parse_mode="md")
    
    # 假设 scan_duplicate_messages 返回一个字典 {类型: 数量}
    deleted_counts = await session_manager.scan_duplicate_messages(event.chat_id)
    
    report = "**🗑️ 去重扫描完成**\n\n"
    if deleted_counts:
        total = 0
        for media_type, count in deleted_counts.items():
            report += f"- {media_type}: {count} 条\n"
            total += count
        if total == 0:
             report += "没有发现重复消息。"
    else:
        report += "没有发现重复消息。"
        
    await msg.edit(report)
    
async def handle_dedup_command(event):
    # Same as above.
    pass

async def handle_admin_panel_command(event):
    # This usually involves buttons, might be complex. Stub for now.
    await reply_and_delete(event, "Admin panel coming soon.")

async def handle_update_command(event):
    """处理 /update 命令，手动触发更新"""
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("🔍 正在检查更新...", parse_mode="md")
    
    has_update, remote_ver = await update_service.check_for_updates(force=True)
    
    if not has_update:
        # [Fix Loop] 如果没有更新，明确告知用户并提供强制更新选项
        from telethon import Button
        buttons = [
            [Button.inline("⚡ 强制重新部署", "confirm_update"), Button.inline("❌ 关闭", "delete")]
        ]
        await msg.edit(
            f"✅ **当前已是最新版本**\n\n当前版本: `{remote_ver}`\n\n如果您遇到系统异常或文件损坏，可以尝试强制重新部署。",
            buttons=buttons
        )
        return

    # [Fix Loop] 添加二次确认按钮
    from telethon import Button
    buttons = [
        [Button.inline("🚀 确认更新", "confirm_update"), Button.inline("❌ 取消", "delete")]
    ]
    await msg.edit(f"🆕 **检测到新版本**: `{remote_ver}`\n\n是否立即执行更新并重启？", buttons=buttons)
    
    # Logic moved to callback_confirm_update to prevent auto-execution

async def callback_confirm_update(event):
    """处理确认更新回调"""
    msg = await event.edit("🚀 正在执行更新流程，请稍候...", buttons=None)
    
    success, result_msg = await update_service.perform_update()
    
    if success:
        # 主动触发一次 Bot 命令注册
        try:
             from telethon.tl.functions.bots import SetBotCommandsRequest
             from telethon.tl.types import BotCommandScopeDefault
             from handlers.bot_commands_list import BOT_COMMANDS
             await event.client(SetBotCommandsRequest(
                 scope=BotCommandScopeDefault(),
                 lang_code='en',
                 commands=BOT_COMMANDS
             ))
        except Exception as e:
             logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

        await msg.edit(f"🚀 **系统更新成功！**\n\n{result_msg}\n\n系统将在 3 秒后自动重启。")
        await asyncio.sleep(3)
        from services.system_service import guard_service
        guard_service.trigger_restart()
    else:
        await msg.edit(f"❌ **更新失败**\n\n原因: `{result_msg}`")

async def handle_rollback_command(event):
    """紧急回滚命令"""
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("🚑 正在启动紧急回滚流程...", parse_mode="md")
    
    success, result_msg = await update_service.rollback()
    
    if success:
        await msg.edit(f"🏥 **回滚指令执行成功**\n\n{result_msg}\n\n正在强制重启...")
        await asyncio.sleep(2)
        from services.system_service import guard_service
        guard_service.trigger_restart()
    else:
        await msg.edit(f"❌ **回滚失败**\n\n原因: `{result_msg}`")

async def handle_history_command(event):
    """显示更新历史"""
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    msg = await event.respond("📖 正在获取版本历史...", parse_mode="md")
    
    history = await update_service.get_update_history(limit=5)
    
    if not history:
        await msg.edit("⚠️ 无法获取版本历史 (可能不是 Git 仓库或暂无记录)")
        return
        
    text = "**📖 历史版本 (最近 5 条)**\n\n"
    for item in history:
        text += f"🔹 `{item['short_sha']}` - {item['author']}\n"
        text += f"📅 `{item['timestamp']}`\n"
        text += f"📝 {item['message']}\n"
        text += f"回滚: `/rollback {item['sha']}`\n\n"
        
    await msg.edit(text)

async def handle_targeted_rollback_command(event, parts):
    """回滚命令：支持无参(自动回滚至上个版本)或有参(指定 Commit SHA)"""
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    
    if len(parts) < 1:
        msg = await event.respond("🚑 正在启动紧急回滚流程 (自动恢复上个本地记录)...", parse_mode="md")
        success, result_msg = await update_service.rollback()
        
        if success:
            await msg.edit(f"🏥 **回滚指令执行成功**\n\n{result_msg}\n\n正在强制重启...")
            await asyncio.sleep(2)
            from services.system_service import guard_service
            guard_service.trigger_restart()
        else:
            await msg.edit(f"❌ **回滚失败**\n\n原因: `{result_msg}`")
        return
        
    sha = parts[0]
    msg = await event.respond(f"🚑 正在请求定向回滚到版本 `{sha[:8]}`...", parse_mode="md")
    # 定向回滚通过 Supervisor 重新同步代码
    await update_service.trigger_update(target_version=sha)
