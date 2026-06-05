from core.helpers.auto_delete import reply_and_delete

async def handle_cancel_command(event):
    """处理 cancel 命令 - 退出交互式会话"""
    from services.session_service import session_manager
    user_session = session_manager.user_sessions.get(event.sender_id, {})
    
    if event.chat_id in user_session:
        user_session.pop(event.chat_id)
        if not user_session:
             if event.sender_id in session_manager.user_sessions:
                 del session_manager.user_sessions[event.sender_id]
        await reply_and_delete(event, "✅ 已退出当前会话模式。")
    else:
        await reply_and_delete(event, "当前没有活跃的会话模式。")
