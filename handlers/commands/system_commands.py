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
    
    duplicates = await session_manager.scan_duplicate_messages(event)
    
    report = "**🗑️ 去重扫描完成**\n\n"
    if duplicates:
        total = 0
        for sig, msg_ids in duplicates.items():
            count = len(msg_ids)
            report += f"- `{sig[:8]}`: {count} 条\n"
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

async def handle_update_command(event, parts=None):
    """处理 /update [target] 命令，手动触发更新"""
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    
    target = parts[0] if parts else "origin/main"
    
    msg = await event.respond(f"🔍 正在检查针对 `{target}` 的更新...", parse_mode="md")
    
    # 获取当前版本信息
    has_update, remote_ver = await update_service.check_for_updates(force=True)
    from version import get_version
    current_sha = await update_service.get_current_version()
    version_str = get_version()
    
    from telethon import Button
    text = (
        f"🚀 **系统更新/重部署确认**\n\n"
        f"目标版本/分支: `{target}`\n"
        f"状态: {'发现新版本' if has_update else '当前已是最新或强制重新部署'}（{remote_ver}）\n"
        f"当前版本：{version_str}（{current_sha}）\n\n"
        f"操作影响: \n"
        f"1. 数据库自动备份\n"
        f"2. 守护进程同步代码\n"
        f"3. 自动安装缺失依赖\n"
        f"4. 系统自动重启并应用迁移\n\n"
        f"确定要开始吗？"
    )
    
    buttons = [
        [Button.inline("🚀 确认执行", data=f"confirm_update:{target}"), Button.inline("❌ 取消", data="cancel")]
    ]
    await msg.edit(text, buttons=buttons)

async def callback_confirm_update(event, target=None, **kwargs):
    """处理确认更新回调"""
    # 优先使用 router 参数，其次解析 data
    if not target:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        target = parts[1] if len(parts) > 1 else "origin/main"
    
    await event.edit(f"🚀 **正在触发系统更新序列...**\n\n目标: `{target}`\n\n系统将由于更新重启，请在 60 秒后重新连接。", buttons=None)
    await asyncio.sleep(2)
    
    # 调用 trigger_update (会引发 sys.exit)
    await update_service.trigger_update(target_version=target)

async def handle_rollback_command(event):
    """触发回滚确认"""
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    
    from telethon import Button
    text = (
        "🚑 **紧急回滚确认**\n\n"
        "操作影响: \n"
        "1. 尝试回退至上一个本地 Git 版本记录\n"
        "2. 若 Git 失败则从物理备份还原文件\n"
        "3. 系统强制重启\n\n"
        "⚠️ **警告**: 此操作仅限系统崩溃无法自愈时使用。"
    )
    
    buttons = [
        [Button.inline("⚠️ 确认强制回滚", data="confirm_rollback"), Button.inline("❌ 取消", data="cancel")]
    ]
    await event.respond(text, buttons=buttons)

async def callback_confirm_rollback(event, **kwargs):
    """处理确认回滚回调"""
    await event.edit("🚑 **正在触发紧急回滚序列...**\n\n系统将立即重启以进行文件恢复。", buttons=None)
    await asyncio.sleep(2)
    
    # 复用 UpdateService 的请求回滚逻辑
    await update_service.request_rollback()

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
        text += f"回滚至此: `/update {item['sha']}`\n\n"
        
    await msg.edit(text)
