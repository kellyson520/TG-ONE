import logging
from filters.base_filter import BaseFilter
from filters.keyword_filter import KeywordFilter
from utils.helpers.common import check_keywords
from utils.helpers.common import get_main_module
from ai import get_ai_provider
from utils.core.constants import DEFAULT_AI_MODEL,DEFAULT_SUMMARY_PROMPT,DEFAULT_AI_PROMPT
from datetime import datetime, timedelta
import asyncio
import re
import base64
import os
import io
import mimetypes
from utils.core.error_handler import handle_errors, handle_telegram_errors, log_execution

logger = logging.getLogger(__name__)

class AIFilter(BaseFilter):
    """
    AI处理过滤器，使用AI处理消息文本
    """
    
    async def _process(self, context):
        """
        使用AI处理消息文本
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        message_text = context.message_text
        original_message_text = context.original_message_text
        event = context.event

        try:
            if not rule.is_ai:
                logger.info("AI处理未开启，返回原始消息")
                return True

            # 处理媒体组消息
            if context.is_media_group:
                logger.info(f"is_media_group: {context.is_media_group}")
            
            # 获取需要上传的图片文件
            image_files = []
            has_media_to_process = False
            
            if rule.enable_ai_upload_image:
                # 检查是否有已下载的媒体文件
                if context.media_files:
                    # 已经下载好的文件，需要读取到内存
                    for file_path in context.media_files:
                        image_data = await self._load_file_to_memory(file_path)
                        if image_data:
                            image_files.append(image_data)
                            
                    has_media_to_process = len(image_files) > 0
                    logger.info(f"已加载 {len(image_files)} 个文件到内存")
                    
                # 如果没有已下载的文件，但有媒体组消息，则直接下载到内存
                elif context.is_media_group and context.media_group_messages:
                    logger.info(f"检测到媒体组消息: {len(context.media_group_messages)}条，直接下载到内存")
                    # 下载媒体组中的图片到内存
                    for msg in context.media_group_messages:
                        if msg.photo or (msg.document and hasattr(msg.document, 'mime_type') and msg.document.mime_type.startswith('image/')):
                            image_data = await self._download_media_to_memory(msg)
                            if image_data:
                                image_files.append(image_data)
                    
                    has_media_to_process = len(image_files) > 0
                    logger.info(f"共下载了 {len(image_files)} 张图片到内存")
                    
                # 检查单条消息是否有媒体并下载到内存
                elif event.message and event.message.media:
                    logger.info("检测到单条消息有媒体，下载到内存")
                    try:
                        # 创建内存缓冲区
                        buffer = io.BytesIO()
                        # 直接下载到内存
                        await event.message.download_media(file=buffer)
                        # 获取图片内容
                        buffer.seek(0)
                        content = buffer.read()
                        
                        # 获取MIME类型
                        mime_type = "image/jpeg"  # 默认类型
                        if hasattr(event.message.media, 'photo'):
                            mime_type = "image/jpeg"
                        elif hasattr(event.message.media, 'document') and hasattr(event.message.media.document, 'mime_type'):
                            mime_type = event.message.media.document.mime_type
                        
                        # 保存到内存图片列表
                        image_files.append({
                            "data": base64.b64encode(content).decode('utf-8'),
                            "mime_type": mime_type
                        })
                        has_media_to_process = True
                        logger.info(f"已下载单条消息媒体到内存，类型: {mime_type}，大小: {len(content) // 1024} KB")
                    except Exception as e:
                        logger.error(f"下载单条消息媒体到内存时出错: {str(e)}")
            
            # 如果有消息文本或图片，使用AI处理
            if context.message_text or has_media_to_process:
                try:
                    # 确保即使没有文本也能处理图片
                    text_to_process = context.message_text if context.message_text else "[图片消息]"
                    
                    logger.info(f"开始AI处理，文本长度: {len(text_to_process)}，图片数量: {len(image_files)}")
                    processed_text = await _ai_handle(text_to_process, rule, image_files)
                    context.message_text = processed_text

                    
                    # 如果需要在AI处理后再次检查关键字
                    logger.info(f"rule.is_keyword_after_ai:{rule.is_keyword_after_ai}")
                    if rule.is_keyword_after_ai:
                        should_forward = await check_keywords(rule, processed_text, event)
                        
                        if not should_forward:
                            logger.info('AI处理后的文本未通过关键字检查，取消转发')
                            context.should_forward = False
                            return False
                except Exception as e:
                    logger.error(f'AI处理消息时出错: {str(e)}')
                    context.errors.append(f"AI处理错误: {str(e)}")
                    # 即使AI处理失败，仍然继续处理
            return True 
        finally:
            pass


async def _ai_handle(message: str, rule, image_files=None) -> str:
    """使用AI处理消息
    
    Args:
        message: 原始消息文本
        rule: 转发规则对象，包含AI相关设置
        image_files: 需要上传的图片文件路径列表或内存中的图片数据
        
    Returns:
        str: 处理后的消息文本
    """
    try:
        if not rule.is_ai:
            logger.info("AI处理未开启，返回原始消息")
            return message
        # 先读取数据库，如果ai模型为空，则使用.env中的默认模型
        if not rule.ai_model:
            rule.ai_model = DEFAULT_AI_MODEL
            logger.info(f"使用默认AI模型: {rule.ai_model}")
        else:
            logger.info(f"使用规则配置的AI模型: {rule.ai_model}")
            
        provider = await get_ai_provider(rule.ai_model)
        
        if not rule.ai_prompt:
            rule.ai_prompt = DEFAULT_AI_PROMPT
            logger.info("使用默认AI提示词")
        else:
            logger.info("使用规则配置的AI提示词")
        
        # 处理特殊提示词格式
        prompt = rule.ai_prompt
        if prompt:
            # 处理聊天记录提示词
            
            # 匹配源聊天和目标聊天的context格式
            source_context_match = re.search(r'\{source_message_context:(\d+)\}', prompt)
            target_context_match = re.search(r'\{target_message_context:(\d+)\}', prompt)
            # 匹配源聊天和目标聊天的time格式
            source_time_match = re.search(r'\{source_message_time:(\d+)\}', prompt)
            target_time_match = re.search(r'\{target_message_time:(\d+)\}', prompt)
            
            if any([source_context_match, target_context_match, source_time_match, target_time_match]):
                
                main = await get_main_module()
                client = main.user_client
                
                # 获取源聊天和目标聊天ID（使用统一解析）
                from utils.helpers.id_utils import resolve_entity_by_id_variants
                try:
                    _, source_chat_id = await resolve_entity_by_id_variants(client, rule.source_chat.telegram_chat_id)
                    _, target_chat_id = await resolve_entity_by_id_variants(client, rule.target_chat.telegram_chat_id)
                    
                    # 回退处理
                    if source_chat_id is None:
                        source_chat_id = int(rule.source_chat.telegram_chat_id)
                    if target_chat_id is None:
                        target_chat_id = int(rule.target_chat.telegram_chat_id)
                        
                except Exception as id_error:
                    logger.warning(f"解析聊天ID失败，使用原始值: {str(id_error)}")
                    source_chat_id = int(rule.source_chat.telegram_chat_id)
                    target_chat_id = int(rule.target_chat.telegram_chat_id)
                
                # 处理源聊天的消息获取
                if source_context_match:
                    count = int(source_context_match.group(1))
                    chat_history = await _get_chat_messages(client, source_chat_id, count=count)
                    prompt = prompt.replace(source_context_match.group(0), chat_history)
                    
                if source_time_match:
                    minutes = int(source_time_match.group(1))
                    chat_history = await _get_chat_messages(client, source_chat_id, minutes=minutes)
                    prompt = prompt.replace(source_time_match.group(0), chat_history)
                
                # 处理目标聊天的消息获取
                if target_context_match:
                    count = int(target_context_match.group(1))
                    chat_history = await _get_chat_messages(client, target_chat_id, count=count)
                    prompt = prompt.replace(target_context_match.group(0), chat_history)
                    
                if target_time_match:
                    minutes = int(target_time_match.group(1))
                    chat_history = await _get_chat_messages(client, target_chat_id, minutes=minutes)
                    prompt = prompt.replace(target_time_match.group(0), chat_history)
            
            # 替换消息占位符
            if '{Message}' in prompt:
                prompt = prompt.replace('{Message}', message)
                
        logger.info(f"处理后的AI提示词: {prompt}")
        
        # 处理图片上传 - 新版本，支持内存中的图片数据
        img_data = []
        if rule.enable_ai_upload_image and image_files and len(image_files) > 0:
            # 检查图片是否已经是内存格式
            if isinstance(image_files[0], dict) and "data" in image_files[0] and "mime_type" in image_files[0]:
                # 已经是内存格式，直接使用
                img_data = image_files
                logger.info(f"使用内存中的图片数据，共有 {len(img_data)} 张图片")
            else:
                # 文件路径格式，需要读取文件
                for img_file in image_files:
                    try:
                        logger.info("准备从文件读取图片")
                        with open(img_file, "rb") as f:
                            img_bytes = f.read()
                            encoded_img = base64.b64encode(img_bytes).decode('utf-8')
                            
                            # 获取MIME类型
                            mime_type = "image/jpeg"  # 默认类型
                            if str(img_file).lower().endswith(".png"):
                                mime_type = "image/png"
                            elif str(img_file).lower().endswith(".gif"):
                                mime_type = "image/gif"
                            elif str(img_file).lower().endswith(".webp"):
                                mime_type = "image/webp"
                                
                            img_data.append({
                                "data": encoded_img,
                                "mime_type": mime_type
                            })
                            # 记录图片大小而不是内容
                            logger.info(f"已读取图片，类型: {mime_type}，大小: {len(img_bytes) // 1024} KB")
                    except Exception as e:
                        logger.error("读取图片文件时出错")
        
        logger.info(f"共有 {len(img_data)} 张图片将上传到AI")
        
        processed_text = await provider.process_message(
            message=message,
            prompt=prompt,
            model=rule.ai_model,
            images=img_data if img_data else None
        )
        logger.info(f"AI处理完成: {processed_text}")
        # 兜底：当返回为空或以错误提示开头时，保留原文
        try:
            if not processed_text:
                return message
            lower = str(processed_text).strip().lower()
            if lower.startswith("ai处理失败") or lower.startswith("ai處理失敗") or lower.startswith("ai failed"):
                return message
        except Exception:
            return message
        return processed_text
        
    except Exception as e:
        logger.error(f"AI处理消息时出错: {str(e)}")
        return message


async def _get_chat_messages(client, chat_id, minutes=None, count=None, delay_seconds: float = 0.5) -> str:
    """获取聊天记录 - 官方API优化版本
    
    Args:
        client: Telegram客户端
        chat_id: 聊天ID
        minutes: 获取最近几分钟的消息
        count: 获取最新的几条消息
        delay_seconds: 每条消息获取之间的延迟秒数，默认0.5秒（优化版本中减少使用）
        
    Returns:
        str: 聊天记录文本
    """
    try:
        # 使用优化的批量消息获取API
        from utils.network.api_optimization import get_api_optimizer
        api_optimizer = get_api_optimizer()
        
        limit = count if count else 500  # 设置一个合理的默认值
        
        if api_optimizer:
            logger.info(f"使用官方API批量获取聊天消息: chat_id={chat_id}, limit={limit}")
            
            if minutes:
                # 使用API优化器的时间范围消息获取
                end_time = datetime.now()
                start_time = end_time - timedelta(minutes=minutes)
                
                # 使用批量获取方法
                messages_data = await api_optimizer.get_messages_batch(
                    chat_id, 
                    limit=limit
                )
                
                # 筛选时间范围内的文本消息
                text_messages = []
                for msg in messages_data:
                    if hasattr(msg, 'date') and msg.date and hasattr(msg, 'text') and msg.text:
                        if msg.date >= start_time:
                            text_messages.append(msg.text)
                
                logger.info(f"批量获取到 {len(messages_data)} 条消息，筛选出 {len(text_messages)} 条文本消息")
                return "\n---\n".join(text_messages) if text_messages else ""
            
            else:
                # 获取指定数量的最新消息
                messages_data = await api_optimizer.get_messages_batch(
                    chat_id, 
                    limit=limit
                )
                
                # 提取文本消息
                text_messages = []
                for msg in messages_data:
                    if hasattr(msg, 'text') and msg.text:
                        text_messages.append(msg.text)
                
                logger.info(f"批量获取到 {len(messages_data)} 条消息，提取出 {len(text_messages)} 条文本消息")
                return "\n---\n".join(text_messages) if text_messages else ""
        
        # 降级处理：如果API优化器不可用，使用传统方法但增加错误提示
        else:
            logger.warning("API优化器未初始化，使用传统消息获取方法")
            messages = []
            processed_count = 0
            
            if minutes:
                # 计算时间范围
                end_time = datetime.now()
                start_time = end_time - timedelta(minutes=minutes)
                
                # 获取指定时间范围内的消息
                async for message in client.iter_messages(
                    chat_id,
                    limit=limit,
                    offset_date=end_time,
                    reverse=True
                ):
                    if message.date < start_time:
                        break
                    if message.text:
                        messages.append(message.text)
                        processed_count += 1
                        if processed_count % 50 == 0:  # 减少休息频率以提升性能
                            await asyncio.sleep(delay_seconds * 0.5)  # 减少延迟
            else:
                # 获取指定数量的最新消息
                async for message in client.iter_messages(
                    chat_id,
                    limit=count
                ):
                    if message.text:
                        messages.append(message.text)
                        processed_count += 1
                        if processed_count % 50 == 0:  # 减少休息频率
                            await asyncio.sleep(delay_seconds * 0.5)  # 减少延迟
                    
            return "\n---\n".join(messages) if messages else ""
        
    except Exception as e:
        logger.error(f"获取聊天记录时出错: {str(e)}")
        return ""
    
    @handle_errors(default_return=None)
    async def _load_file_to_memory(self, file_path):
        """
        安全地将文件加载到内存
        
        Args:
            file_path: 文件路径
            
        Returns:
            dict: 包含图片数据和MIME类型的字典，失败时返回None
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return None
            
        # 读取文件内容
        with open(file_path, 'rb') as f:
            file_content = f.read()
            
        # 获取MIME类型
        mime_type = mimetypes.guess_type(file_path)[0] or "image/jpeg"
        
        logger.info(f"已加载图片到内存，类型: {mime_type}，大小: {len(file_content) // 1024} KB")
        
        # 返回图片数据
        return {
            "data": base64.b64encode(file_content).decode('utf-8'),
            "mime_type": mime_type
        }
    
    @handle_errors(default_return=None)
    async def _download_media_to_memory(self, message):
        """
        安全地将消息中的媒体下载到内存
        
        Args:
            message: Telegram消息对象
            
        Returns:
            dict: 包含图片数据和MIME类型的字典，失败时返回None
        """
        # 创建内存缓冲区
        buffer = io.BytesIO()
        
        # 直接下载到内存缓冲区
        await message.download_media(file=buffer)
        
        # 获取图片内容
        buffer.seek(0)
        content = buffer.read()
        
        # 获取MIME类型
        mime_type = "image/jpeg"  # 默认类型
        if message.photo:
            mime_type = "image/jpeg"
        elif message.document and hasattr(message.document, 'mime_type'):
            mime_type = message.document.mime_type
        
        logger.info(f"已下载媒体到内存，类型: {mime_type}，大小: {len(content) // 1024} KB")
        
        # 返回图片数据
        return {
            "data": base64.b64encode(content).decode('utf-8'),
            "mime_type": mime_type
        }
