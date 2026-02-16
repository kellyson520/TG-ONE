from typing import Any

def detect_message_type(message: Any) -> str:
    """
    智能化检测 Telethon 消息类型
    
    Args:
        message: Telethon Message 对象
        
    Returns:
        str: 消息类型字符串 (text, photo, video, document, gif, voice, audio, sticker, video_note, contact, location, poll, game)
    """
    if not message:
        return "unknown"
        
    if getattr(message, 'photo', None):
        return "photo"
    if getattr(message, 'video', None):
        return "video"
    if getattr(message, 'document', None):
        # 进一步细分 document
        if getattr(message, 'gif', None):
            return "gif"
        if getattr(message, 'voice', None):
            return "voice"
        if getattr(message, 'audio', None):
            return "audio"
        if getattr(message, 'sticker', None):
            return "sticker"
        if getattr(message, 'video_note', None):
            return "video_note"
        return "document"
    
    # 其他类型
    if getattr(message, 'contact', None):
        return "contact"
    if getattr(message, 'location', None) or getattr(message, 'geo', None):
        return "location"
    if getattr(message, 'poll', None):
        return "poll"
    if getattr(message, 'game', None):
        return "game"
    
    # 默认文本
    if getattr(message, 'text', None) or not getattr(message, 'media', None):
        return "text"
        
    return "unknown"
