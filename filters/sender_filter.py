import logging
import os
from filters.base_filter import BaseFilter
from enums.enums import PreviewMode
from telethon.errors import FloodWaitError
from utils.helpers.common import get_main_module
from utils.core.error_handler import handle_telegram_errors, handle_errors
from utils.db.db_context import safe_db_operation

logger = logging.getLogger(__name__)

class SenderFilter(BaseFilter):
    """
    消息发送过滤器，用于发送处理后的消息
    """
    
    async def _process(self, context):
        """
        发送处理后的消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        client = context.client
        event = context.event
        
        if not context.should_forward:
            logger.info('消息不满足转发条件，跳过发送')
            return False
        
        if rule.enable_only_push:
            logger.info('只转发到推送配置，跳过发送')
            return True
            
        # 获取目标聊天信息（兼容映射：若无 rule.target_chat，则从映射或缓存中读取）
        target_chat = getattr(rule, 'target_chat', None)
        if target_chat is None:
            # 使用统一的数据库操作获取目标聊天
            target_chat = await self._get_target_chat(rule)

        if not target_chat:
            logger.error('无法确定目标聊天，取消发送')
            return False

        from utils.helpers.id_utils import resolve_entity_by_id_variants
        target_chat_id = int(target_chat.telegram_chat_id)
        try:
            entity, resolved_id = await resolve_entity_by_id_variants(client, target_chat_id)
            if resolved_id is not None:
                target_chat_id = resolved_id
            if entity is not None:
                logger.info(f'成功获取目标聊天实体: {target_chat.name} (ID: {target_chat_id})')
        except Exception as e:
            logger.warning(f'获取目标聊天实体时出错: {str(e)}')
        
        # 设置消息格式
        parse_mode = rule.message_mode.value  # 使用枚举的值（字符串）
        logger.info(f'使用消息格式: {parse_mode}')
        
        # 使用统一的错误处理发送消息
        success = await self._send_message_with_error_handling(context, target_chat_id, target_chat, parse_mode)
        return success

    async def _forward_pure(self, context, target_chat_id):
        """使用用户客户端进行纯转发，不下载后再上传。
        同时在不启用推送时清理已下载的临时文件（若前序过滤器已下载）。
        """
        rule = context.rule
        event = context.event
        context.forwarded_messages = []

        # 获取客户端 (优先使用上下文中的客户端)
        user_client = context.client
        if user_client is None:
            # 尝试从全局获取
            main = await get_main_module()
            user_client = getattr(main, 'user_client', None)
            
        if user_client is None:
            raise RuntimeError('无法获取客户端进行纯转发')

        try:
            if event.message.grouped_id:
                # 优先使用已收集的媒体组消息ID
                message_ids = []
                if context.media_group_messages:
                    message_ids = sorted([m.id for m in context.media_group_messages])
                else:
                    # 使用统一媒体组管理器获取消息
                    message_ids = []
                    try:
                        from services.media_service import media_service
                        
                        if media_service:
                            # 使用媒体服务获取
                            messages = await media_service.get_media_group_messages(
                                event.chat_id, event.message.id, event.message.grouped_id
                            )
                            message_ids = [msg.id for msg in messages]
                            logger.info(f"媒体服务找到 {len(message_ids)} 条媒体组消息")
                        else:
                            # 降级到传统方法
                            logger.warning("媒体组管理器未初始化，使用传统方法")
                            async for message in user_client.iter_messages(
                                event.chat_id,
                                limit=20,
                                min_id=event.message.id - 10,
                                max_id=event.message.id + 10
                            ):
                                if message.grouped_id == event.message.grouped_id:
                                    message_ids.append(message.id)
                        
                    except Exception as e:
                        logger.warning(f"媒体组管理器获取失败，使用传统方法: {e}")
                        # 降级到传统方法
                        async for message in user_client.iter_messages(
                            event.chat_id,
                            limit=20,
                            min_id=event.message.id - 10,
                            max_id=event.message.id + 10
                        ):
                            if message.grouped_id == event.message.grouped_id:
                                message_ids.append(message.id)
                    
                    message_ids.sort()

                from utils.processing.forward_queue import forward_messages_queued
                sent = await forward_messages_queued(
                    user_client,
                    source_chat_id=event.chat_id,
                    target_chat_id=target_chat_id,
                    messages=message_ids
                )
                # 保存到上下文（保持 list 语义）
                if isinstance(sent, list):
                    context.forwarded_messages = sent
                else:
                    context.forwarded_messages = [sent]
                logger.info(f'纯转发媒体组 {len(message_ids)} 条消息完成')
                
                # 记录转发信息
                await self._record_forward(context, target_chat_id, event.message.id)
            else:
                from utils.processing.forward_queue import forward_messages_queued
                sent = await forward_messages_queued(
                    user_client,
                    source_chat_id=event.chat_id,
                    target_chat_id=target_chat_id,
                    messages=event.message.id
                )
                context.forwarded_messages = [sent] if not isinstance(sent, list) else sent
                logger.info('纯转发单条消息完成')
                
                # 记录转发信息
                await self._record_forward(context, target_chat_id, event.message.id)
        finally:
            # 若未启用推送，清理前序过滤器可能下载的文件
            try:
                if not getattr(rule, 'enable_push', False) and getattr(context, 'media_files', None):
                    for file_path in list(context.media_files):
                        try:
                            if os.path.exists(str(file_path)):
                                os.remove(file_path)
                                logger.info(f'纯转发模式清理临时文件: {file_path}')
                        except Exception as e:
                            logger.error(f'纯转发模式删除临时文件失败: {str(e)}')
            except Exception:
                pass

        # 记录媒体签名（作为发送成功的凭证），便于后续去重
        try:
            if hasattr(context, 'dup_signatures') and context.dup_signatures:
                from services.dedup_service import dedup_service
                target_chat_id = int(context.rule.target_chat.telegram_chat_id)
                # Note: This is a bit low-level, but consistent with current refactor
                for sig, mid in set(context.dup_signatures):
                    await dedup_service.repo.add_or_update(
                        chat_id=str(target_chat_id),
                        signature=sig,
                        message_id=mid
                    )
        except Exception as e:
            logger.warning(f'纯转发后记录媒体签名失败: {str(e)}')
    
    async def _send_media_group(self, context, target_chat_id, parse_mode):
        """发送媒体组消息"""
        rule = context.rule
        client = context.client
        event = context.event
        # 初始化转发消息列表
        context.forwarded_messages = []
        
        # if not context.media_group_messages:
        #     logger.info(f'所有媒体都超限，发送文本和提示')
        #     # 构建提示信息
        #     text_to_send = context.message_text or ''

        #     # 设置原始消息链接
        #     context.original_link = f"\n原始消息: https://t.me/c/{str(event.chat_id)[4:]}/{event.message.id}"
            
        #     # 添加每个超限文件的信息
        #     for message, size, name in context.skipped_media:
        #         text_to_send += f"\n\n⚠️ 媒体文件 {name if name else '未命名文件'} ({size}MB) 超过大小限制"
            
        #     # 组合完整文本
        #     text_to_send = context.sender_info + text_to_send + context.time_info + context.original_link
            
        #     await client.send_message(
        #         target_chat_id,
        #         text_to_send,
        #         parse_mode=parse_mode,
        #         link_preview=True,
        #         buttons=context.buttons
        #     )
        #     logger.info(f'媒体组所有文件超限，已发送文本和提示')
        #     return
            
        # 如果有可以发送的媒体，作为一个组发送
        files = []
        try:
            # 纯转发模式下不下载，直接交给上游逻辑（此分支仅在非纯转发时执行）
            if not getattr(context.rule, 'force_pure_forward', False):
                for message in context.media_group_messages:
                    if message.media:
                        file_path = await message.download_media(os.path.join(os.getcwd(), 'temp'))
                        if file_path:
                            files.append(file_path)
            
            # 修改：保存下载的文件路径到context.media_files
            if files:
                # 初始化 media_files 如果它不存在
                if not hasattr(context, 'media_files') or context.media_files is None:
                    context.media_files = []
                # 将当前下载的文件添加到列表中
                context.media_files.extend(files)
                logger.info(f'已将 {len(files)} 个下载的媒体文件路径保存到context.media_files')
                
                # 添加发送者信息和消息文本
                caption_text = context.sender_info + context.message_text
                
                # 如果有超限文件，添加提示信息
                for message, size, name in context.skipped_media:
                    caption_text += f"\n\n⚠️ 媒体文件 {name if name else '未命名文件'} ({size}MB) 超过大小限制"
                
                if context.skipped_media:
                    context.original_link = f"\n原始消息: https://t.me/c/{str(event.chat_id)[4:]}/{event.message.id}"
                # 添加时间信息和原始链接
                caption_text += context.time_info + context.original_link
                
                # 作为一个组发送所有文件
                sent_messages = await client.send_file(
                    target_chat_id,
                    files,
                    caption=caption_text,
                    parse_mode=parse_mode,
                    buttons=context.buttons,
                    link_preview={
                        PreviewMode.ON: True,
                        PreviewMode.OFF: False,
                        PreviewMode.FOLLOW: context.event.message.media is not None
                    }[rule.is_preview]
                )
                # 保存发送的消息到上下文
                # 修复："Updates" 对象没有 len() 方法的问题
                if isinstance(sent_messages, list):
                    context.forwarded_messages = sent_messages
                elif hasattr(sent_messages, 'updates') and sent_messages.updates:
                    # 处理 Updates 对象
                    updates = sent_messages.updates
                    if isinstance(updates, list):
                        # 如果 updates 是列表，提取其中的消息
                        messages = [u.message for u in updates if hasattr(u, 'message') and u.message]
                        context.forwarded_messages = messages if messages else [sent_messages]
                    else:
                        context.forwarded_messages = [sent_messages]
                else:
                    context.forwarded_messages = [sent_messages]
                
                logger.info(f'媒体组消息已发送，保存了 {len(context.forwarded_messages)} 条已转发消息')
        except Exception as e:
            logger.error(f'发送媒体组消息时出错: {str(e)}')
            raise
        finally:
            # 删除临时文件，但如果启用了推送则保留
            if not rule.enable_push:
                for file_path in files:
                    try:
                        os.remove(file_path)
                        logger.info(f'删除临时文件: {file_path}')
                    except Exception as e:
                        logger.error(f'删除临时文件失败: {str(e)}')
            else:
                logger.info(f'推送功能已启用，保留临时文件')
    
    async def _send_single_media(self, context, target_chat_id, parse_mode):
        """发送单条媒体消息"""
        rule = context.rule
        client = context.client
        event = context.event
        
        logger.info(f'发送单条媒体消息')
        
        # 检查是否所有媒体都超限
        if context.skipped_media and not context.media_files:
            # 构建提示信息
            file_size = context.skipped_media[0][1]
            file_name = context.skipped_media[0][2]
            original_link = f"\n原始消息: https://t.me/c/{str(event.chat_id)[4:]}/{event.message.id}"
            
            text_to_send = context.message_text or ''
            text_to_send += f"\n\n⚠️ 媒体文件 {file_name} ({file_size}MB) 超过大小限制"
            text_to_send = context.sender_info + text_to_send + context.time_info
            
            text_to_send += original_link
                
            await client.send_message(
                target_chat_id,
                text_to_send,
                parse_mode=parse_mode,
                link_preview=True,
                buttons=context.buttons
            )
            logger.info(f'媒体文件超过大小限制，仅转发文本')
            return
        
        # 确保context.media_files存在
        if not hasattr(context, 'media_files') or context.media_files is None:
            context.media_files = []
        
        # 发送媒体文件
        for file_path in context.media_files:
            try:
                caption = (
                    context.sender_info + 
                    context.message_text + 
                    context.time_info + 
                    context.original_link
                )
                
                await client.send_file(
                    target_chat_id,
                    file_path,
                    caption=caption,
                    parse_mode=parse_mode,
                    buttons=context.buttons,
                    link_preview={
                        PreviewMode.ON: True,
                        PreviewMode.OFF: False,
                        PreviewMode.FOLLOW: context.event.message.media is not None
                    }[rule.is_preview]
                )
                logger.info(f'媒体消息已发送')
            except Exception as e:
                logger.error(f'发送媒体消息时出错: {str(e)}')
                raise
            finally:
                # 删除临时文件，但如果启用了推送则保留
                if not rule.enable_push:
                    try:
                        os.remove(file_path)
                        logger.info(f'删除临时文件: {file_path}')
                    except Exception as e:
                        logger.error(f'删除临时文件失败: {str(e)}')
                else:
                    logger.info(f'推送功能已启用，保留临时文件: {file_path}')
    
    async def _send_text_message(self, context, target_chat_id, parse_mode):
        """发送纯文本消息"""
        rule = context.rule
        client = context.client
        
        if not context.message_text:
            logger.info('没有文本内容，不发送消息')
            return
            
        # 根据预览模式设置 link_preview
        link_preview = {
            PreviewMode.ON: True,
            PreviewMode.OFF: False,
            PreviewMode.FOLLOW: context.event.message.media is not None  # 跟随原消息
        }[rule.is_preview]
        
        # 组合消息文本
        message_text = context.sender_info + context.message_text + context.time_info + context.original_link
        
        await client.send_message(
            target_chat_id,
            str(message_text),
            parse_mode=parse_mode,
            link_preview=link_preview,
            buttons=context.buttons
        )
        logger.info(f'{"带预览的" if link_preview else "无预览的"}文本消息已发送')
    
    @handle_errors(default_return=None)
    async def _get_target_chat(self, rule):
        """
        获取目标聊天信息 - 使用统一的数据库管理
        
        Args:
            rule: 转发规则
            
        Returns:
            Chat对象或None
        """
        def get_chat_operation(session):
            from models.models import Chat
            target_chat_id = getattr(rule, 'target_chat_id', None)
            if target_chat_id:
                return session.query(Chat).get(target_chat_id)
            return None
        
        return safe_db_operation(get_chat_operation, default_return=None)
    
    @handle_errors(default_return=False)
    async def _send_message_with_error_handling(self, context, target_chat_id, target_chat, parse_mode):
        """
        使用统一的错误处理发送消息
        
        Args:
            context: 消息上下文
            target_chat_id: 目标聊天ID
            target_chat: 目标聊天对象
            parse_mode: 解析模式
            
        Returns:
            bool: 是否发送成功
        """
        rule = context.rule
        
        try:
            # 若启用强制纯转发，则统一使用 forward_messages
            if getattr(rule, 'force_pure_forward', False):
                logger.info('启用强制纯转发，使用 forward_messages 而非下载后上传')
                await self._forward_pure(context, target_chat_id)
            else:
                # 处理媒体组消息
                if context.is_media_group or (context.media_group_messages and context.skipped_media):
                    logger.info(f'准备发送媒体组消息')
                    await self._send_media_group(context, target_chat_id, parse_mode)
                # 处理单条媒体消息
                elif context.media_files or context.skipped_media:
                    logger.info(f'准备发送单条媒体消息')
                    await self._send_single_media(context, target_chat_id, parse_mode)
                # 处理纯文本消息
                else:
                    logger.info(f'准备发送纯文本消息')
                    await self._send_text_message(context, target_chat_id, parse_mode)
                
            logger.info(f'消息已发送到: {target_chat.name} ({target_chat_id})')
            return True
            
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.error(f'发送消息频率限制，需要等待 {wait_time} 秒')
            context.errors.append(f"发送消息频率限制，需要等待 {wait_time} 秒")
            return False
        except Exception as e:
            # 添加详细的错误日志记录
            error_msg = str(e).lower()
            if 'protected chat' in error_msg or 'forwardmessagesrequest' in error_msg:
                logger.error(f"受保护的聊天内容错误: 无法转发受保护的聊天内容，规则ID={getattr(rule, 'id', 'Unknown')}，目标聊天ID={target_chat_id}")
            elif 'invalid message' in error_msg:
                logger.error(f"消息ID超出范围错误: 尝试转发的消息ID超出范围或不存在，规则ID={getattr(rule, 'id', 'Unknown')}，目标聊天ID={target_chat_id}")
            else:
                logger.error(f"发送消息时出错: {type(e).__name__} - {str(e)}，规则ID={getattr(rule, 'id', 'Unknown')}，目标聊天ID={target_chat_id}")
            
            context.errors.append(f"发送消息时出错: {str(e)}")
            if hasattr(context, 'failed_rules') and hasattr(rule, 'id'):
                context.failed_rules.append(rule.id)
            return False
    
    async def _record_forward(self, context, target_chat_id, message_id):
        """记录转发信息"""
        try:
            from utils.forward_recorder import forward_recorder
            rule = context.rule
            event = context.event
            
            # 获取原始消息
            main = await get_main_module()
            user_client = getattr(main, 'user_client', None)
            if user_client is None:
                logger.warning("无法获取用户客户端，跳过转发记录")
                return
                
            # 获取原始消息
            original_message = await user_client.get_messages(event.chat_id, ids=message_id)
            if not original_message:
                logger.warning(f"无法获取原始消息 {message_id}，跳过转发记录")
                return
            
            # 记录转发
            await forward_recorder.record_forward(
                message_obj=original_message,
                source_chat_id=event.chat_id,
                target_chat_id=target_chat_id,
                rule_id=rule.id,
                forward_type="auto"
            )
            logger.debug(f"转发记录完成: {message_id}")
        except Exception as e:
            logger.error(f"记录转发失败: {str(e)}")
