"""
高级媒体过滤器
支持时长、分辨率、文件大小范围等精确筛选
"""
import logging
from filters.base_filter import BaseFilter
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio, DocumentAttributeAnimated
from core.helpers.media import get_media_size

logger = logging.getLogger(__name__)

class AdvancedMediaFilter(BaseFilter):
    """高级媒体过滤器，支持精确的媒体属性筛选"""
    
    async def _process(self, context):
        """
        处理高级媒体筛选
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        event = context.event
        message = event.message
        
        # 如果没有媒体，直接通过
        if not message.media:
            return True
        
        # 检查时长过滤
        if rule.enable_duration_filter:
            if not await self._check_duration_filter(message, rule):
                logger.info("消息被时长过滤器拦截")
                return False
        
        # 检查分辨率过滤
        if rule.enable_resolution_filter:
            if not await self._check_resolution_filter(message, rule):
                logger.info("消息被分辨率过滤器拦截")
                return False
        
        # 检查文件大小范围过滤
        if rule.enable_file_size_range:
            if not await self._check_file_size_range_filter(message, rule):
                logger.info("消息被文件大小范围过滤器拦截")
                return False
        
        return True
    
    async def _check_duration_filter(self, message, rule):
        """
        检查时长过滤
        
        Args:
            message: 消息对象
            rule: 转发规则
            
        Returns:
            bool: 是否通过过滤
        """
        duration = await self._get_media_duration(message)
        if duration is None:
            # 无时长信息（如图片、文档等），不参与时长过滤，直接通过
            return True
        
        # 检查最小时长
        if rule.min_duration > 0 and duration < rule.min_duration:
            logger.info(f"媒体时长 {duration}s 小于最小时长 {rule.min_duration}s")
            return False
        
        # 检查最大时长
        if rule.max_duration > 0 and duration > rule.max_duration:
            logger.info(f"媒体时长 {duration}s 大于最大时长 {rule.max_duration}s")
            return False
        
        logger.info(f"媒体时长 {duration}s 通过时长过滤")
        return True
    
    async def _check_resolution_filter(self, message, rule):
        """
        检查分辨率过滤
        
        Args:
            message: 消息对象
            rule: 转发规则
            
        Returns:
            bool: 是否通过过滤
        """
        width, height = await self._get_media_resolution(message)
        if width is None or height is None:
            # 无分辨率信息（如音频、语音等），不参与分辨率过滤，直接通过
            return True
        
        # 检查最小宽度
        if rule.min_width > 0 and width < rule.min_width:
            logger.info(f"媒体宽度 {width} 小于最小宽度 {rule.min_width}")
            return False
        
        # 检查最大宽度
        if rule.max_width > 0 and width > rule.max_width:
            logger.info(f"媒体宽度 {width} 大于最大宽度 {rule.max_width}")
            return False
        
        # 检查最小高度
        if rule.min_height > 0 and height < rule.min_height:
            logger.info(f"媒体高度 {height} 小于最小高度 {rule.min_height}")
            return False
        
        # 检查最大高度
        if rule.max_height > 0 and height > rule.max_height:
            logger.info(f"媒体高度 {height} 大于最大高度 {rule.max_height}")
            return False
        
        logger.info(f"媒体分辨率 {width}x{height} 通过分辨率过滤")
        return True
    
    async def _check_file_size_range_filter(self, message, rule):
        """
        检查文件大小范围过滤
        
        Args:
            message: 消息对象
            rule: 转发规则
            
        Returns:
            bool: 是否通过过滤
        """
        file_size_mb = await get_media_size(message)
        if file_size_mb is None:
            # 无法获取大小信息时不拦截，直接通过
            return True
        
        file_size_kb = file_size_mb * 1024  # 转换为KB
        
        # 检查最小文件大小
        if rule.min_file_size > 0 and file_size_kb < rule.min_file_size:
            logger.info(f"文件大小 {file_size_kb:.1f}KB 小于最小大小 {rule.min_file_size}KB")
            return False
        
        # 检查最大文件大小
        if rule.max_file_size > 0 and file_size_kb > rule.max_file_size:
            logger.info(f"文件大小 {file_size_kb:.1f}KB 大于最大大小 {rule.max_file_size}KB")
            return False
        
        logger.info(f"文件大小 {file_size_kb:.1f}KB 通过大小范围过滤")
        return True
    
    async def _get_media_duration(self, message):
        """
        获取媒体时长
        
        Args:
            message: 消息对象
            
        Returns:
            int: 时长（秒），如果没有时长信息返回None
        """
        media = message.media
        
        # 处理视频
        if hasattr(media, 'document') and media.document:
            for attr in media.document.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    return attr.duration
                elif isinstance(attr, DocumentAttributeAudio):
                    return attr.duration
                elif isinstance(attr, DocumentAttributeAnimated):
                    return getattr(attr, 'duration', None)
        
        # 处理音频
        elif hasattr(media, 'audio') and media.audio:
            return getattr(media.audio, 'duration', None)
        
        # 处理语音
        elif hasattr(media, 'voice') and media.voice:
            return getattr(media.voice, 'duration', None)
        
        return None
    
    async def _get_media_resolution(self, message):
        """
        获取媒体分辨率
        
        Args:
            message: 消息对象
            
        Returns:
            tuple: (宽度, 高度)，如果没有分辨率信息返回(None, None)
        """
        media = message.media
        
        # 处理图片
        if hasattr(media, 'photo') and media.photo:
            # 获取最大尺寸的图片
            largest_size = None
            largest_bytes = 0
            
            for size in media.photo.sizes:
                if hasattr(size, 'size') and size.size > largest_bytes:
                    largest_size = size
                    largest_bytes = size.size
                elif hasattr(size, 'sizes') and isinstance(size.sizes, list):
                    max_size = max(size.sizes) if size.sizes else 0
                    if max_size > largest_bytes:
                        largest_size = size
                        largest_bytes = max_size
            
            if largest_size and hasattr(largest_size, 'w') and hasattr(largest_size, 'h'):
                return largest_size.w, largest_size.h
        
        # 处理视频和动画
        elif hasattr(media, 'document') and media.document:
            for attr in media.document.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    return attr.w, attr.h
                elif isinstance(attr, DocumentAttributeAnimated):
                    return getattr(attr, 'w', None), getattr(attr, 'h', None)
        
        return None, None
    
    async def _format_duration(self, seconds):
        """格式化时长显示"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}分{secs}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}时{minutes}分{secs}秒"
    
    async def _format_file_size(self, kb):
        """格式化文件大小显示"""
        if kb < 1024:
            return f"{kb:.1f}KB"
        elif kb < 1024 * 1024:
            return f"{kb/1024:.1f}MB"
        else:
            return f"{kb/1024/1024:.1f}GB"
