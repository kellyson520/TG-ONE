"""
全局过滤器
处理全局媒体筛选设置，应用于所有规则
"""
import logging
import re
from filters.base_filter import BaseFilter

logger = logging.getLogger(__name__)

class GlobalFilter(BaseFilter):
    """
    全局过滤器，处理全局媒体筛选设置
    这个过滤器应用全局配置，优先于规则级别的设置
    """
    
    async def _process(self, context):
        """
        处理全局媒体筛选
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        event = context.event
        message = event.message
        
        # 获取全局媒体设置
        try:
            from handlers.button.forward_management import forward_manager
            settings = await forward_manager.get_global_media_settings()
        except Exception as e:
            logger.error(f"获取全局设置失败: {str(e)}")
            return True  # 如果获取设置失败，继续处理
        
        # 检查是否有实际媒体
        has_media = (
            message.media and
            any([
                getattr(message.media, 'photo', None),
                getattr(message.media, 'document', None),
                getattr(message.media, 'video', None),
                getattr(message.media, 'audio', None),
                getattr(message.media, 'voice', None)
            ])
        )
        
        # 检查文本消息
        is_text = (message.message and not has_media)
        if is_text:
            # 检查是否允许文本
            if not settings.get('allow_text', True):
                logger.info('全局设置：文本消息被屏蔽')
                context.should_forward = False
                return False
                
            # 检查是否允许表情包
            if not settings.get('allow_emoji', True):
                # 检查是否是纯表情包消息（只包含emoji和空格）
                text = message.message.strip() if message.message else ""
                if text:
                    # 使用正则表达式检查是否只包含emoji和空格
                    emoji_pattern = re.compile(
                        r"["
                        r"\U0001F600-\U0001F64F"  # Emoticons
                        r"\U0001F300-\U0001F5FF"  # Symbols & Pictographs
                        r"\U0001F680-\U0001F6FF"  # Transport & Map
                        r"\U0001F1E6-\U0001F1FF"  # Flags
                        r"\U00002700-\U000027BF"  # Dingbats
                        r"\U0001F900-\U0001F9FF"  # Supplemental Symbols
                        r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                        r"\U0001F000-\U0001F0FF"  # Mahjong, etc
                        r"\u2600-\u26FF"          # Misc symbols
                        r"\u2300-\u23FF"          # Misc technical
                        r"\u2B50"                 # Star
                        r"\u200d\ufe0f"           # ZWJ/Variation
                        r"\s"                     # Spaces
                        r"]+", 
                        flags=re.UNICODE
                    )
                    # 如果消息只包含emoji和空格，则认为是表情包消息
                    if emoji_pattern.fullmatch(text):
                        logger.info('全局设置：表情包消息被屏蔽')
                        context.should_forward = False
                        return False
        
        # 如果没有媒体，直接通过
        if not has_media:
            return True
        
        # 检查媒体类型（全局设置）
        media_types = settings.get('media_types', {})
        
        # 检查图片
        if getattr(message.media, 'photo', None):
            if not media_types.get('image', True):
                logger.info('全局设置：图片类型被屏蔽')
                if settings.get('allow_text', True):
                    context.media_blocked = True  # 标记媒体被屏蔽，但允许文本
                else:
                    context.should_forward = False
                    return False
        
        # 检查语音
        elif getattr(message.media, 'voice', None):
            if not media_types.get('voice', True):
                logger.info('全局设置：语音类型被屏蔽')
                if settings.get('allow_text', True):
                    context.media_blocked = True
                else:
                    context.should_forward = False
                    return False
        
        # 检查音频
        elif getattr(message.media, 'audio', None):
            if not media_types.get('audio', True):
                logger.info('全局设置：音频类型被屏蔽')
                if settings.get('allow_text', True):
                    context.media_blocked = True
                else:
                    context.should_forward = False
                    return False
        
        # 检查文档（包括视频文档）
        elif getattr(message.media, 'document', None):
            doc = message.media.document
            attrs = getattr(doc, 'attributes', []) or []
            is_video = False
            is_audio = False
            
            from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio
            # 检查文档属性
            for a in attrs:
                if isinstance(a, DocumentAttributeVideo):
                    is_video = True
                    break
                elif isinstance(a, DocumentAttributeAudio):
                    is_audio = True
                    break
            
            if is_video:
                if not media_types.get('video', True):
                    logger.info('全局设置：视频文档被屏蔽')
                    if settings.get('allow_text', True):
                        context.media_blocked = True
                    else:
                        context.should_forward = False
                        return False
            elif is_audio:
                if not media_types.get('audio', True):
                    logger.info('全局设置：音频文档被屏蔽')
                    if settings.get('allow_text', True):
                        context.media_blocked = True
                    else:
                        context.should_forward = False
                        return False
            else:
                if not media_types.get('document', True):
                    logger.info('全局设置：文档类型被屏蔽')
                    if settings.get('allow_text', True):
                        context.media_blocked = True
                    else:
                        context.should_forward = False
                        return False
        
        # 检查原生视频（较少见）
        elif getattr(message.media, 'video', None):
            if not media_types.get('video', True):
                logger.info('全局设置：原生视频被屏蔽')
                if settings.get('allow_text', True):
                    context.media_blocked = True
                else:
                    context.should_forward = False
                    return False


        
        # 检查媒体时长（全局设置）
        if settings.get('media_duration_enabled', False):
            min_seconds = int(settings.get('duration_min_seconds', 0) or 0)
            max_seconds = int(settings.get('duration_max_seconds', 0) or 0)
            duration = None
            
            # 获取时长
            if getattr(message.media, 'voice', None) and hasattr(message.media.voice, 'duration'):
                duration = message.media.voice.duration
            elif getattr(message.media, 'audio', None) and hasattr(message.media.audio, 'duration'):
                duration = message.media.audio.duration
            elif getattr(message.media, 'video', None) and hasattr(message.media.video, 'duration'):
                duration = message.media.video.duration
            elif getattr(message.media, 'document', None):
                doc = message.media.document
                attrs = getattr(doc, 'attributes', []) or []
                for a in attrs:
                    if a.__class__.__name__ == 'DocumentAttributeVideo':
                        duration = getattr(a, 'duration', None)
                        break
                    elif a.__class__.__name__ == 'DocumentAttributeAudio':
                        duration = getattr(a, 'duration', None)
                        break
            
            if duration is not None:
                if duration < min_seconds:
                    logger.info(f'全局设置：媒体时长 {duration}s 小于最小时长 {min_seconds}s')
                    if settings.get('allow_text', True):
                        context.media_blocked = True
                    else:
                        context.should_forward = False
                        return False
                if max_seconds > 0 and duration > max_seconds:
                    logger.info(f'全局设置：媒体时长 {duration}s 大于最大时长 {max_seconds}s')
                    if settings.get('allow_text', True):
                        context.media_blocked = True
                    else:
                        context.should_forward = False
                        return False
        
        # 检查媒体大小（全局设置）
        if settings.get('media_size_filter_enabled', False):
            try:
                from core.helpers.media import get_media_size
                file_size = await get_media_size(message.media)
                file_size_mb = round(file_size/1024/1024, 2)
                size_limit = settings.get('media_size_limit', 100)
                
                if file_size_mb > size_limit:
                    logger.info(f'全局设置：媒体大小 {file_size_mb}MB 超过限制 {size_limit}MB')
                    if settings.get('allow_text', True):
                        context.media_blocked = True
                    else:
                        context.should_forward = False
                        return False
            except Exception as e:
                logger.warning(f"检查媒体大小失败: {str(e)}")
        
        # 检查媒体扩展名（全局设置）
        if settings.get('media_extension_enabled', False):
            try:
                extensions = settings.get('media_extensions', [])
                filter_mode = settings.get('extension_filter_mode', 'blacklist')
                
                if getattr(message.media, 'document', None) and extensions:
                    doc = message.media.document
                    file_name = None
                    
                    # 获取文件名
                    for attr in getattr(doc, 'attributes', []):
                        if hasattr(attr, 'file_name'):
                            file_name = attr.file_name
                            break
                    
                    if file_name:
                        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
                        
                        if filter_mode == 'blacklist':
                            # 黑名单模式：扩展名在列表中则屏蔽
                            if file_ext in extensions:
                                logger.info(f'全局设置：扩展名 {file_ext} 在黑名单中')
                                if settings.get('allow_text', True):
                                    context.media_blocked = True
                                else:
                                    context.should_forward = False
                                    return False
                        else:
                            # 白名单模式：扩展名不在列表中则屏蔽
                            if file_ext not in extensions:
                                logger.info(f'全局设置：扩展名 {file_ext} 不在白名单中')
                                if settings.get('allow_text', True):
                                    context.media_blocked = True
                                else:
                                    context.should_forward = False
                                    return False
            except Exception as e:
                logger.warning(f"检查媒体扩展名失败: {str(e)}")
        
                logger.warning(f"检查媒体扩展名失败: {str(e)}")
        
        # [Bug Fix] 将媒体屏蔽处理移至最后，确保覆盖所有检查（时长、大小等）
        # 如果媒体被屏蔽但允许文本，将媒体去除，仅保留文本（若有）
        if getattr(context, 'media_blocked', False):
            try:
                # 标记为不要转发媒体，后续发送阶段可据此仅发文本
                # 如果没有文本，should_forward 将变为 False
                context.should_forward = bool(getattr(message, 'message', '').strip())
                if context.should_forward:
                    logger.info("全局设置：媒体被屏蔽，仅转发文本")
                else:
                    logger.info("全局设置：媒体被屏蔽且无文本，取消转发")
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        
        return True
