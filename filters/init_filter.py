import logging
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    pytz = None
    PYTZ_AVAILABLE = False

from filters.base_filter import BaseFilter

logger = logging.getLogger(__name__)

class InitFilter(BaseFilter):
    """
    初始化过滤器，为context添加基本信息
    """
    
    async def _process(self, context):
        """
        添加原始链接和发送者信息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        event = context.event

        # logger.info(f"InitFilter处理消息前，context: {context.__dict__}")
        try:
            #处理媒体组消息
            if event.message.grouped_id:
                # 等待更长时间让所有媒体消息到达
                # await asyncio.sleep(1)
                
                # 收集媒体组的所有消息
                try:
                    async for message in event.client.iter_messages(
                        event.chat_id,
                        limit=20,
                        min_id=event.message.id - 10,
                        max_id=event.message.id + 10
                    ):
                        if message.grouped_id == event.message.grouped_id:
                            if message.text:    
                                # 保存第一条消息的文本和按钮
                                context.message_text = message.text or ''
                                context.original_message_text = message.text or ''
                                context.check_message_text = message.text or ''
                                context.buttons = message.buttons if hasattr(message, 'buttons') else None
                            logger.info(f'获取到媒体组文本并添加到context: {message.text}')
                        
                except Exception as e:
                    logger.error(f'收集媒体组消息时出错: {str(e)}')
                    context.errors.append(f"收集媒体组消息错误: {str(e)}")

            # 生成去重签名（不做判重，仅先生成并放入上下文）
            try:
                context.dup_signatures = []
                if event.message.grouped_id and context.media_group_messages:
                    for msg in context.media_group_messages:
                        sig = None
                        try:
                            # 统一的签名规则：
                            # - photo: 使用最大尺寸的 (w x h) 与字节大小
                            # - video: 使用 (duration, w x h, size)
                            # - document: 使用 (mime_type, size, filename)
                            if getattr(msg, 'photo', None):
                                sizes = getattr(msg.photo, 'sizes', []) or []
                                # 计算最大字节数与对应宽高
                                best = None
                                best_bytes = 0
                                for s in sizes:
                                    b = 0
                                    if hasattr(s, 'size') and isinstance(getattr(s, 'size'), int):
                                        b = s.size
                                    elif hasattr(s, 'sizes') and isinstance(getattr(s, 'sizes'), list):
                                        try:
                                            b = max(s.sizes)
                                        except Exception:
                                            b = 0
                                    if b >= best_bytes:
                                        best = s
                                        best_bytes = b
                                w = getattr(best, 'w', None) if best else None
                                h = getattr(best, 'h', None) if best else None
                                sig = f"photo:{w or ''}x{h or ''}:{best_bytes}"
                            elif getattr(msg, 'document', None):
                                doc = msg.document
                                attrs = getattr(doc, 'attributes', []) or []
                                # 检测是否为视频
                                video_attr = None
                                file_name = None
                                for a in attrs:
                                    name = a.__class__.__name__
                                    if name == 'DocumentAttributeVideo':
                                        video_attr = a
                                    if hasattr(a, 'file_name'):
                                        file_name = a.file_name
                                if video_attr:
                                    duration = getattr(video_attr, 'duration', None)
                                    vw = getattr(video_attr, 'w', None)
                                    vh = getattr(video_attr, 'h', None)
                                    size_bytes = getattr(doc, 'size', None) or 0
                                    sig = f"video:{duration or ''}s:{vw or ''}x{vh or ''}:{size_bytes}"
                                else:
                                    mime = getattr(doc, 'mime_type', None) or ''
                                    size_bytes = getattr(doc, 'size', None) or 0
                                    fn = (file_name or '').lower()
                                    sig = f"document:{mime}:{size_bytes}:{fn}"
                        except Exception:
                            sig = None
                        if sig:
                            context.dup_signatures.append((sig, msg.id))
                else:
                    m = event.message
                    sig = None
                    try:
                        if getattr(m, 'photo', None):
                            sizes = getattr(m.photo, 'sizes', []) or []
                            best = None
                            best_bytes = 0
                            for s in sizes:
                                b = 0
                                if hasattr(s, 'size') and isinstance(getattr(s, 'size'), int):
                                    b = s.size
                                elif hasattr(s, 'sizes') and isinstance(getattr(s, 'sizes'), list):
                                    try:
                                        b = max(s.sizes)
                                    except Exception:
                                        b = 0
                                if b >= best_bytes:
                                    best = s
                                    best_bytes = b
                            w = getattr(best, 'w', None) if best else None
                            h = getattr(best, 'h', None) if best else None
                            sig = f"photo:{w or ''}x{h or ''}:{best_bytes}"
                        elif getattr(m, 'document', None):
                            doc = m.document
                            attrs = getattr(doc, 'attributes', []) or []
                            video_attr = None
                            file_name = None
                            for a in attrs:
                                name = a.__class__.__name__
                                if name == 'DocumentAttributeVideo':
                                    video_attr = a
                                if hasattr(a, 'file_name'):
                                    file_name = a.file_name
                            if video_attr:
                                duration = getattr(video_attr, 'duration', None)
                                vw = getattr(video_attr, 'w', None)
                                vh = getattr(video_attr, 'h', None)
                                size_bytes = getattr(doc, 'size', None) or 0
                                sig = f"video:{duration or ''}s:{vw or ''}x{vh or ''}:{size_bytes}"
                            else:
                                mime = getattr(doc, 'mime_type', None) or ''
                                size_bytes = getattr(doc, 'size', None) or 0
                                fn = (file_name or '').lower()
                                sig = f"document:{mime}:{size_bytes}:{fn}"
                    except Exception:
                        sig = None
                    if sig:
                        context.dup_signatures.append((sig, m.id))
            except Exception as e:
                logger.warning(f'生成去重签名失败: {str(e)}')
           
        finally:
            # logger.info(f"InitFilter处理消息后，context: {context.__dict__}")
            return True
