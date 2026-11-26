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
        """处理全局媒体筛选"""
        event = context.event
        message = event.message

        try:
            from handlers.button.forward_management import forward_manager
            settings = await forward_manager.get_global_media_settings()
        except Exception as e:
            logger.error(f"获取全局设置失败: {str(e)}")
            return True

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

        is_text = (message.message and not has_media)
        if is_text:
            block_result = self._check_text_filter(message, settings, context)
            if block_result is not None:
                return block_result

        if not has_media:
            return True

        if not self._check_media_type_filter(message, settings, context):
            return False

        if not await self._check_media_duration(message, settings, context):
            return False

        if not await self._check_media_size(message, settings, context):
            return False

        if not self._check_media_extension(message, settings, context):
            return False

        if getattr(context, 'media_blocked', False):
            try:
                context.should_forward = bool(getattr(message, 'message', '').strip())
                if context.should_forward:
                    logger.info("全局设置：媒体被屏蔽，仅转发文本")
                else:
                    logger.info("全局设置：媒体被屏蔽且无文本，取消转发")
                    context.errors.append("全局过滤：媒体屏蔽且无文本")
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}')
            return context.should_forward

        return True

    def _check_text_filter(self, message, settings, context):
        """检查文本消息过滤（文本/表情包屏蔽）"""
        if not settings.get('allow_text', True):
            logger.info('全局设置：文本消息被屏蔽')
            context.should_forward = False
            context.errors.append("全局过滤：禁止文本消息")
            return False

        if not settings.get('allow_emoji', True):
            text = message.message.strip() if message.message else ""
            if text:
                emoji_pattern = re.compile(
                    r"["
                    r"\U0001F600-\U0001F64F"
                    r"\U0001F300-\U0001F5FF"
                    r"\U0001F680-\U0001F6FF"
                    r"\U0001F1E6-\U0001F1FF"
                    r"\U00002700-\U000027BF"
                    r"\U0001F900-\U0001F9FF"
                    r"\U0001FA70-\U0001FAFF"
                    r"\U0001F000-\U0001F0FF"
                    r"\u2600-\u26FF"
                    r"\u2300-\u23FF"
                    r"\u2B50"
                    r"\u200d\ufe0f"
                    r"\s"
                    r"]+",
                    flags=re.UNICODE
                )
                if emoji_pattern.fullmatch(text):
                    logger.info('全局设置：表情包消息被屏蔽')
                    context.should_forward = False
                    context.errors.append("全局过滤：禁止表情包")
                    return False

        return None

    def _check_media_type_filter(self, message, settings, context):
        """检查媒体类型过滤（图片/语音/音频/文档/视频）"""
        media_types = settings.get('media_types', {})

        type_checks = [
            ('photo', 'image'),
            ('voice', 'voice'),
            ('audio', 'audio'),
            ('video', 'video'),
        ]
        for media_attr, type_key in type_checks:
            if getattr(message.media, media_attr, None):
                if not media_types.get(type_key, True):
                    logger.info(f'全局设置：{type_key}类型被屏蔽')
                    return self._apply_block(settings, context)

        if getattr(message.media, 'document', None):
            return self._check_document_type(message.media.document, media_types, settings, context)

        return True

    def _check_document_type(self, doc, media_types, settings, context):
        """检查文档子类型（视频/音频/sticker/普通文档）"""
        attrs = getattr(doc, 'attributes', []) or []

        from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio
        is_video = is_audio = is_sticker_attr = False
        for a in attrs:
            if a.__class__.__name__ == 'DocumentAttributeSticker':
                is_sticker_attr = True
                break
            elif isinstance(a, DocumentAttributeVideo):
                is_video = True
                break
            elif isinstance(a, DocumentAttributeAudio):
                is_audio = True
                break

        if is_sticker_attr:
            type_key = 'document'
            label = '表情包(sticker)'
        elif is_video:
            type_key = 'video'
            label = '视频文档'
        elif is_audio:
            type_key = 'audio'
            label = '音频文档'
        else:
            type_key = 'document'
            label = '文档'

        if not media_types.get(type_key, True):
            logger.info(f'全局设置：{label}类型被屏蔽')
            return self._apply_block(settings, context)

        return True

    def _apply_block(self, settings, context):
        """根据 allow_text 设置决定屏蔽行为"""
        if settings.get('allow_text', True):
            context.media_blocked = True
            return True
        else:
            context.should_forward = False
            return False

    async def _check_media_duration(self, message, settings, context):
        """检查媒体时长过滤"""
        if not settings.get('media_duration_enabled', False):
            return True

        min_seconds = int(settings.get('duration_min_seconds', 0) or 0)
        max_seconds = int(settings.get('duration_max_seconds', 0) or 0)
        duration = self._extract_duration(message.media)

        if duration is not None:
            if duration < min_seconds:
                logger.info(f'全局设置：媒体时长 {duration}s 小于最小时长 {min_seconds}s')
                return self._apply_block(settings, context)
            if max_seconds > 0 and duration > max_seconds:
                logger.info(f'全局设置：媒体时长 {duration}s 大于最大时长 {max_seconds}s')
                return self._apply_block(settings, context)

        return True

    def _extract_duration(self, media):
        """从媒体对象中提取时长"""
        for attr_name in ('voice', 'audio', 'video'):
            obj = getattr(media, attr_name, None)
            if obj and hasattr(obj, 'duration'):
                return obj.duration

        doc = getattr(media, 'document', None)
        if doc:
            for a in getattr(doc, 'attributes', []) or []:
                if a.__class__.__name__ in ('DocumentAttributeVideo', 'DocumentAttributeAudio'):
                    return getattr(a, 'duration', None)

        return None

    async def _check_media_size(self, message, settings, context):
        """检查媒体大小过滤"""
        if not settings.get('media_size_filter_enabled', False):
            return True

        try:
            from core.helpers.media import get_media_size
            file_size = await get_media_size(message.media)
            file_size_mb = round(file_size / 1024 / 1024, 2)
            size_limit = settings.get('media_size_limit', 100)

            if file_size_mb > size_limit:
                logger.info(f'全局设置：媒体大小 {file_size_mb}MB 超过限制 {size_limit}MB')
                return self._apply_block(settings, context)
        except Exception as e:
            logger.warning(f"检查媒体大小失败: {str(e)}")

        return True

    def _check_media_extension(self, message, settings, context):
        """检查媒体扩展名过滤"""
        if not settings.get('media_extension_enabled', False):
            return True

        try:
            extensions = settings.get('media_extensions', [])
            filter_mode = settings.get('extension_filter_mode', 'blacklist')

            if not (getattr(message.media, 'document', None) and extensions):
                return True

            doc = message.media.document
            file_name = None
            for attr in getattr(doc, 'attributes', []):
                if hasattr(attr, 'file_name'):
                    file_name = attr.file_name
                    break

            if not file_name:
                return True

            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''

            if filter_mode == 'blacklist' and file_ext in extensions:
                logger.info(f'全局设置：扩展名 {file_ext} 在黑名单中')
                return self._apply_block(settings, context)
            elif filter_mode != 'blacklist' and file_ext not in extensions:
                logger.info(f'全局设置：扩展名 {file_ext} 不在白名单中')
                return self._apply_block(settings, context)
        except Exception as e:
            logger.warning(f"检查媒体扩展名失败: {str(e)}")

        return True
