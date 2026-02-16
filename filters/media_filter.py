import logging
import os
from core.helpers.media import get_media_size
from core.constants import TEMP_DIR
from filters.base_filter import BaseFilter
from models.models import MediaTypes
# AsyncSessionManager is deprecated, use container.db.get_session() instead
from core.helpers.common import get_db_ops
from enums.enums import AddMode
from services.network.telegram_api_optimizer import api_optimizer
from services.media_service import media_service, extract_message_signature
logger = logging.getLogger(__name__)

class MediaFilter(BaseFilter):
    """
    媒体过滤器
    处理媒体类型筛选、扩展名筛选和大小筛选
    """
    
    async def _process(self, context):
        """
        处理媒体筛选
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        event = context.event
        
        # 如果没有媒体或不启用媒体筛选，直接通过
        if not event.message.media or (not rule.enable_media_type_filter and 
                                      not rule.enable_extension_filter and 
                                      not rule.enable_media_size_filter):
            return True
            
        # 检查是否是媒体组消息
        if event.message.grouped_id:
            logger.info('处理媒体组消息')
            await self._process_media_group(context)
        else:
            logger.info('处理单条媒体消息')
            await self._process_single_media(context)
            
        return True

    async def _process_media_group(self, context):
        """处理媒体组消息"""
        event = context.event
        rule = context.rule
        
        # 初始化媒体组消息列表和跳过媒体列表
        context.media_group_messages = []
        context.skipped_media = []
        
        # 获取媒体类型设置
        from core.container import container
        from sqlalchemy import select
        async with container.db.get_session() as session:
            stmt = select(MediaTypes).filter_by(rule_id=rule.id)
            result = await session.execute(stmt)
            media_types = result.scalar_one_or_none()
            
        total_media_count = 0
        blocked_media_count = 0
        try:
            manager = media_service
            messages = []
            if manager:
                messages = await manager.get_media_group_messages(event.chat_id, event.message.id, event.message.grouped_id)
            else:
                async for m in event.client.iter_messages(
                    event.chat_id,
                    limit=20,
                    min_id=event.message.id - 10,
                    max_id=event.message.id + 10
                ):
                    if m.grouped_id == event.message.grouped_id:
                        messages.append(m)

            selected = []
            for message in messages:
                if message.media:
                    total_media_count += 1
                    if rule.enable_media_type_filter and media_types and message.media:
                        if await self._is_media_type_blocked(message.media, media_types):
                            blocked_media_count += 1
                            continue
                    if rule.enable_extension_filter and message.media:
                        if not await self._is_media_extension_allowed(rule, message.media):
                            blocked_media_count += 1
                            continue
                    file_size = await self._get_media_size_optimized(message.media, event.client)
                    file_size = round(file_size/1024/1024, 2)
                    if rule.max_media_size and (file_size > rule.max_media_size) and rule.enable_media_size_filter:
                        file_name = ''
                        if hasattr(message.media, 'document') and message.media.document:
                            for attr in message.media.document.attributes:
                                if hasattr(attr, 'file_name'):
                                    file_name = attr.file_name
                                    break
                        context.skipped_media.append((message, file_size, file_name))
                        continue
                selected.append(message)

            deduped = []
            seen_fid = set()
            seen_sig = set()
            context.dup_signatures = []
            for msg in selected:
                sig, fid = extract_message_signature(msg)
                if fid is not None:
                    if fid in seen_fid:
                        continue
                    seen_fid.add(fid)
                    context.dup_signatures.append((f"fid:{fid}", msg.id))
                elif sig:
                    if sig in seen_sig:
                        continue
                    seen_sig.add(sig)
                    context.dup_signatures.append((sig, msg.id))
                deduped.append(msg)

            context.media_group_messages = deduped
            for m in deduped:
                logger.info(f'找到媒体组消息: ID={m.id}, 类型={type(m.media).__name__ if m.media else "无媒体"}')
        except Exception as e:
            logger.error(f'收集媒体组消息时出错: {str(e)}')
            context.errors.append(f"收集媒体组消息错误: {str(e)}")
        
        logger.info(f'共找到 {len(context.media_group_messages)} 条媒体组消息，{len(context.skipped_media)} 条超限')
        
        # 如果所有媒体都被屏蔽，设置不转发
        if total_media_count > 0 and total_media_count == blocked_media_count:
            logger.info('媒体组中所有媒体都被屏蔽，设置不转发')
            # 检查是否允许文本通过
            if rule.media_allow_text:
                logger.info('媒体被屏蔽但允许文本通过')
                context.media_blocked = True  # 标记媒体被屏蔽
            else:
                context.should_forward = False
                context.errors.append("媒体过滤：所有媒体被屏蔽")
            return True
            
        # 如果所有媒体都超限且不发送超限提醒，则设置不转发
        if len(context.skipped_media) > 0 and len(context.media_group_messages) == 0 and not rule.is_send_over_media_size_message:
            # 检查是否允许文本通过
            if rule.media_allow_text:
                logger.info('媒体超限但允许文本通过')
                context.media_blocked = True  # 标记媒体被屏蔽
            else:
                context.should_forward = False
                context.errors.append("媒体过滤：媒体超限且未开启提醒")
                logger.info('所有媒体都超限且不发送超限提醒，设置不转发')
    
    async def _process_single_media(self, context):
        """处理单条媒体消息"""
        event = context.event
        rule = context.rule
        # logger.info(f'context属性: {context.rule.__dict__}')
        # 检查是否是纯链接预览消息
        is_pure_link_preview = (
            event.message.media and
            hasattr(event.message.media, 'webpage') and
            not any([
                getattr(event.message.media, 'photo', None),
                getattr(event.message.media, 'document', None),
                getattr(event.message.media, 'video', None),
                getattr(event.message.media, 'audio', None),
                getattr(event.message.media, 'voice', None)
            ])
        )
        
        # 检查是否有实际媒体
        has_media = (
            event.message.media and
            any([
                getattr(event.message.media, 'photo', None),
                getattr(event.message.media, 'document', None),
                getattr(event.message.media, 'video', None),
                getattr(event.message.media, 'audio', None),
                getattr(event.message.media, 'voice', None)
            ])
        )

        # 处理实际媒体
        if has_media:
            # 检查媒体类型是否被屏蔽
            if rule.enable_media_type_filter:
                media_types = getattr(rule, 'media_types', None)
                if not media_types:
                    from core.container import container
                    async with container.db.get_session() as session:
                        from sqlalchemy import select
                        stmt = select(MediaTypes).filter_by(rule_id=rule.id)
                        result = await session.execute(stmt)
                        media_types = result.scalar_one_or_none()
                
                if media_types and await self._is_media_type_blocked(event.message.media, media_types):
                    logger.info(f'🚫 [媒体过滤器] 媒体类型被屏蔽 (规则ID={rule.id})，原因: 相应媒体项在规则设置中被设为"屏蔽"')
                    # 检查是否允许文本通过
                    if rule.media_allow_text:
                        logger.info('媒体被屏蔽但允许文本通过')
                        context.media_blocked = True  # 标记媒体被屏蔽
                    else:
                        context.should_forward = False
                    return True
            
            # 检查媒体扩展名
            if rule.enable_extension_filter and event.message.media:
                if not await self._is_media_extension_allowed(rule, event.message.media):
                    logger.info(f'媒体扩展名被屏蔽，跳过消息 ID={event.message.id}')
                    # 检查是否允许文本通过
                    if rule.media_allow_text:
                        logger.info('媒体被屏蔽但允许文本通过')
                        context.media_blocked = True  # 标记媒体被屏蔽
                    else:
                        context.should_forward = False
                    return True
            
            # 检查媒体大小 - 使用优化的快速检测
            file_size = await self._get_media_size_optimized(event.message.media, event.client)
            file_size = round(file_size/1024/1024, 2)
            logger.info(f'event.message.document: {event.message.document}')
            
            logger.info(f'媒体文件大小: {file_size}MB (优化检测)')
            logger.info(f'规则最大媒体大小: {rule.max_media_size}MB')
            
            logger.info(f'是否启用媒体大小过滤: {rule.enable_media_size_filter}')
            if rule.max_media_size and (file_size > rule.max_media_size) and rule.enable_media_size_filter:
                file_name = ''
                if event.message.document:
                    # 正确地从文档属性中获取文件名
                    for attr in event.message.document.attributes:
                        if hasattr(attr, 'file_name'):
                            file_name = attr.file_name
                            break
                
                logger.info(f'媒体文件超过大小限制 ({rule.max_media_size}MB)')
                if rule.is_send_over_media_size_message:
                    logger.info(f'是否发送媒体大小超限提醒: {rule.is_send_over_media_size_message}')
                    context.should_forward = True
                else:
                    # 检查是否允许文本通过
                    if rule.media_allow_text:
                        logger.info('媒体超限但允许文本通过')
                        context.media_blocked = True  # 标记媒体被屏蔽
                        context.skipped_media.append((event.message, file_size, file_name))
                        return True  # 跳过后续的媒体下载
                    else:
                        context.should_forward = False
                        context.errors.append("媒体过滤：文件大小超限")
                context.skipped_media.append((event.message, file_size, file_name))
                return True  # 不论如何都跳过后续的媒体下载
            else:
                # 在以下情况统一跳过下载，避免占用磁盘：
                # 1) 只转发到 RSS（由 RSS 模块自行处理下载）
                # 2) 启用"强制纯转发"且未启用推送（纯 forward，不下载不上传）
                if rule.only_rss or (getattr(rule, 'force_pure_forward', False) and not getattr(rule, 'enable_push', False)):
                    logger.info('纯转发/仅RSS模式，跳过媒体下载以节省磁盘空间')
                    # 确保 context.media_files 存在，以便后续处理能正确识别为媒体消息
                    if not hasattr(context, 'media_files') or context.media_files is None:
                        context.media_files = []
                    return True
                try:
                    # 使用优化的媒体下载
                    file_path = await self._download_media_optimized(event.message, TEMP_DIR)
                    if file_path:
                        # 确保 context.media_files 存在
                        if not hasattr(context, 'media_files') or context.media_files is None:
                            context.media_files = []
                        context.media_files.append(file_path)
                        logger.info(f'媒体文件已下载到: {file_path}')
                except Exception as e:
                    logger.error(f'下载媒体文件时出错: {str(e)}')
                    context.errors.append(f"下载媒体文件错误: {str(e)}")
        elif is_pure_link_preview:
            # 记录这是纯链接预览消息
            context.is_pure_link_preview = True
            logger.info('这是一条纯链接预览消息')
        else:
            # 处理其他类型的媒体消息（如纯视频）
            logger.info(f'检测到未分类的媒体类型: {type(event.message.media).__name__ if event.message.media else "无媒体"}')
            # 确保 context.media_files 存在
            if not hasattr(context, 'media_files') or context.media_files is None:
                context.media_files = []
            
    async def _is_media_type_blocked(self, media, media_types):
        """
        检查媒体类型是否被屏蔽
        
        Args:
            media: 媒体对象
            media_types: MediaTypes对象
            
        Returns:
            bool: 如果媒体类型被屏蔽返回True，否则返回False
        """
        # 检查图片
        if getattr(media, 'photo', None) and media_types.photo:
            logger.info('媒体类型为图片，已被屏蔽')
            return True
        
        # 检查文档（需要区分视频文档和普通文档）
        if getattr(media, 'document', None):
            doc = media.document
            attrs = getattr(doc, 'attributes', []) or []
            is_video = False
            is_audio = False
            
            # 检查文档属性
            for a in attrs:
                if a.__class__.__name__ == 'DocumentAttributeVideo':
                    is_video = True
                    break
                elif a.__class__.__name__ == 'DocumentAttributeAudio':
                    is_audio = True
                    break
            
            if is_video and media_types.video:
                logger.info('媒体类型为视频文档，已被屏蔽')
                return True
            elif is_audio and media_types.audio:
                logger.info('媒体类型为音频文档，已被屏蔽')
                return True
            elif not is_video and not is_audio and media_types.document:
                logger.info('媒体类型为文档，已被屏蔽')
                return True
        
        # 检查原生视频（较少见）
        if getattr(media, 'video', None) and media_types.video:
            logger.info('媒体类型为原生视频，已被屏蔽')
            return True
        
        # 检查原生音频
        if getattr(media, 'audio', None) and media_types.audio:
            logger.info('媒体类型为音频，已被屏蔽')
            return True
        
        # 检查语音
        if getattr(media, 'voice', None) and media_types.voice:
            logger.info('媒体类型为语音，已被屏蔽')
            return True
        
        return False 
    
    async def _is_media_extension_allowed(self, rule, media):
        """
        检查媒体扩展名是否被允许
        
        Args:
            rule: 转发规则
            media: 媒体对象
            
        Returns:
            bool: 如果扩展名被允许返回True，否则返回False
        """
        # 如果没有启用扩展名过滤，默认允许
        if not rule.enable_extension_filter:
            return True
            
        # 获取文件名
        file_name = None
     
        for attr in media.document.attributes:
            if hasattr(attr, 'file_name'):
                file_name = attr.file_name
                break

            
        # 如果没有文件名，则无法判断扩展名，默认允许
        if not file_name:
            logger.info("无法获取文件名，无法判断扩展名")
            return True
            
        # 提取扩展名
        _, extension = os.path.splitext(file_name)
        extension = extension.lstrip('.').lower()  # 移除点号并转为小写
        
        # 特殊处理：如果文件没有扩展名，将extension设为特殊值"无扩展名"
        if not extension:
            logger.info(f"文件 {file_name} 没有扩展名")
            extension = "无扩展名"
        else:
            logger.info(f"文件 {file_name} 的扩展名: {extension}")
        
        # 获取规则中保存的扩展名列表
        db_ops = await get_db_ops()
        allowed = True
        try:
            from core.container import container
            async with container.db.get_session() as session:
                # 使用db_operations中的函数获取扩展名列表
                extensions = await db_ops.get_media_extensions(session, rule.id)
                extension_list = [ext["extension"].lower() for ext in extensions]
                
                # 判断是否允许该扩展名
                if rule.extension_filter_mode == AddMode.BLACKLIST:
                    # 黑名单模式：如果扩展名在列表中，则不允许
                    if extension in extension_list:
                        logger.info(f"扩展名 {extension} 在黑名单中，不允许")
                        allowed = False
                    else:
                        logger.info(f"扩展名 {extension} 不在黑名单中，允许")
                        allowed = True
                else:
                    # 白名单模式：如果扩展名不在列表中，则不允许
                    if extension in extension_list:
                        logger.info(f"扩展名 {extension} 在白名单中，允许")
                        allowed = True
                    else:
                        logger.info(f"扩展名 {extension} 不在白名单中，不允许")
                        allowed = False
        except Exception as e:
            logger.error(f"检查媒体扩展名时出错: {str(e)}")
            allowed = True  # 出错时默认允许
            
        return allowed
    
    async def _get_media_size_optimized(self, media, client):
        """
        优化的媒体大小获取方法
        
        Args:
            media: 媒体对象
            client: Telegram客户端
            
        Returns:
            int: 文件大小（字节）
        """
        try:
            # 首先尝试从文档属性直接获取
            if hasattr(media, 'document') and media.document:
                document = media.document
                if hasattr(document, 'size') and document.size:
                    logger.debug(f"从文档属性获取大小: {document.size} bytes")
                    return document.size
                
                # 使用API优化器获取详细信息
                try:
                    media_info = await api_optimizer.get_media_info_fast(client, document)
                    if media_info and 'size' in media_info:
                        logger.debug(f"从优化API获取大小: {media_info['size']} bytes")
                        return media_info['size']
                except Exception as api_error:
                    logger.debug(f"API优化获取失败，回退到传统方法: {api_error}")
            
            # 回退到传统方法
            logger.debug("使用传统方法获取媒体大小")
            return await get_media_size(media)
            
        except Exception as e:
            logger.error(f"优化媒体大小获取失败: {str(e)}")
            # 最终回退
            try:
                return await get_media_size(media)
            except Exception:
                return 0
    
    async def _download_media_optimized(self, message, temp_dir):
        """
        优化的媒体下载方法
        
        Args:
            message: 消息对象
            temp_dir: 临时目录
            
        Returns:
            str: 下载的文件路径，如果失败返回None
        """
        try:
            # 检查是否真的需要下载
            # 某些情况下可以跳过下载，比如只需要文件信息
            
            # 对于大文件，可以考虑分块下载或部分下载
            if hasattr(message, 'document') and message.document:
                file_size = getattr(message.document, 'size', 0)
                
                # 如果文件太大，记录警告但仍尝试下载
                if file_size > 50 * 1024 * 1024:  # 50MB
                    logger.warning(f"大文件下载: {file_size} bytes，可能需要较长时间")
            
            # 使用原有的下载方法
            file_path = await message.download_media(temp_dir)
            if file_path:
                logger.info(f'媒体文件下载完成: {file_path}')
            
            return file_path
            
        except Exception as e:
            logger.error(f'优化媒体下载失败: {str(e)}')
            return None
