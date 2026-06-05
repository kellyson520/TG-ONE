from telethon import Button
from core.logging import get_logger
from core.helpers.auto_delete import async_delete_user_message

logger = get_logger(__name__)

async def handle_admin_panel_command(event):
    """处理 /admin 命令"""
    # 模拟简单的 admin 面板，实际应根据需求扩展
    buttons = [
        [Button.inline("系统状态", "sys_status"), Button.inline("数据库信息", "db_info")],
        [Button.inline("重启 Bot", "restart_bot")]
    ]
    
    await async_delete_user_message(event.client, event.chat_id, event.message.id, 0)
    await event.respond("**🔧 管理员控制面板**", buttons=buttons)
