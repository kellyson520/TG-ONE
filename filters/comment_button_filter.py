import logging
import asyncio
import traceback
from telethon import Button
from filters.base_filter import BaseFilter
from telethon.tl.functions.channels import GetFullChannelRequest
from core.helpers.common import get_main_module
from difflib import SequenceMatcher
logger = logging.getLogger(__name__)

class CommentButtonFilter(BaseFilter):
    """
    评论区按钮过滤器，用于在消息中添加指向关联群组消息的按钮
    """

    async def _process(self, context):
        """为消息添加评论区按钮"""
        if context.rule.only_rss:
            logger.info('只转发到RSS，跳过评论区按钮过滤器')
            return True

        try:
            if not context.rule or not context.rule.enable_comment_button:
                return True

            if not context.original_message_text and not context.event.message.media:
                return True

            try:
                main = await get_main_module()
                client = main.user_client if (main and hasattr(main, 'user_client')) else context.client

                event = context.event
                channel_info = await self._resolve_channel_info(event, client)
                if not channel_info:
                    return False

                channel_entity, channel_username, channel_id_str = channel_info

                if not hasattr(channel_entity, 'broadcast') or not channel_entity.broadcast:
                    return True

                linked_group_id = await self._get_linked_group_id(client, channel_entity)
                if not linked_group_id:
                    return True

                entity_resolver = self._get_entity_resolver()
                linked_group = None
                if entity_resolver:
                    linked_group = await entity_resolver.resolve_single_entity(linked_group_id)
                else:
                    logger.warning("实体解析器未初始化，跳过关联群组处理")

                channel_msg_id = await self._resolve_channel_msg_id(event, client, channel_entity)

                logger.info("等待2秒，确保消息同步完成...")
                await asyncio.sleep(2)

                comment_link = self._build_base_comment_link(channel_username, channel_id_str, channel_msg_id)

                if linked_group:
                    comment_link = await self._refine_comment_link(
                        client, linked_group, linked_group_id, context,
                        comment_link, channel_username, channel_id_str, channel_msg_id, event,
                    )

                    group_link = None
                    if hasattr(linked_group, 'username') and linked_group.username:
                        group_link = f"https://t.me/{linked_group.username}"
                        logger.info(f"生成群组备用链接: {group_link}")

                context.comment_link = comment_link

                if context.is_media_group:
                    logger.info("媒体组消息的评论区按钮将由ReplyFilter处理")
                    return True

                self._add_comment_button(context, comment_link)

            except Exception as e:
                logger.error(f"添加评论区按钮时出错: {str(e)}")
                logger.error(traceback.format_exc())

            return True
        finally:
            pass

    async def _resolve_channel_info(self, event, client):
        """解析频道实体并返回 (entity, username, id_str)"""
        from core.helpers.entity_optimization import get_entity_resolver
        entity_resolver = get_entity_resolver()

        if entity_resolver:
            channel_entity = await entity_resolver.resolve_single_entity(event.chat_id)
        else:
            logger.warning("实体解析器未初始化，跳过评论按钮处理")
            return None

        channel_username = None
        if hasattr(channel_entity, 'username') and channel_entity.username:
            channel_username = channel_entity.username
            logger.info(f"获取到频道用户名: {channel_username}")
        elif hasattr(channel_entity, 'usernames') and channel_entity.usernames:
            for username_obj in channel_entity.usernames:
                if username_obj.active:
                    channel_username = username_obj.username
                    logger.info(f"从 usernames 列表获取到频道用户名: {channel_username}")
                    break

        channel_id_str = str(channel_entity.id)
        if channel_id_str.startswith('-100'):
            channel_id_str = channel_id_str[4:]
        elif channel_id_str.startswith('100'):
            channel_id_str = channel_id_str[3:]

        logger.info(f"处理频道ID: {channel_id_str}")

        return channel_entity, channel_username, channel_id_str

    def _get_entity_resolver(self):
        """获取实体解析器"""
        from core.helpers.entity_optimization import get_entity_resolver
        return get_entity_resolver()

    async def _get_linked_group_id(self, client, channel_entity):
        """获取频道关联群组ID，无关联群组返回None"""
        try:
            full_channel = await client(GetFullChannelRequest(channel_entity))
            if not full_channel.full_chat.linked_chat_id:
                logger.info(f"频道 {channel_entity.id} 没有关联群组，跳过添加评论按钮")
                return None
            return full_channel.full_chat.linked_chat_id
        except Exception as e:
            logger.error(f"获取关联群组消息时出错: {str(e)}")
            logger.debug(f"详细错误信息: {traceback.format_exc()}")
            return None

    async def _resolve_channel_msg_id(self, event, client, channel_entity):
        """解析频道消息ID（处理媒体组取最小ID）"""
        channel_msg_id = event.message.id

        if not (hasattr(event.message, 'grouped_id') and event.message.grouped_id):
            return channel_msg_id

        logger.info(f"检测到媒体组消息，组ID: {event.message.grouped_id}")
        try:
            media_group_messages = []
            async for message in client.iter_messages(
                channel_entity, limit=20,
                offset_date=event.message.date, reverse=False,
            ):
                if (hasattr(message, 'grouped_id') and
                    message.grouped_id == event.message.grouped_id):
                    media_group_messages.append(message)

            if media_group_messages:
                min_id_message = min(media_group_messages, key=lambda x: x.id)
                channel_msg_id = min_id_message.id
                logger.info(f"使用媒体组中ID最小的消息: {channel_msg_id}")
        except Exception as e:
            logger.error(f"获取媒体组消息失败: {e}")
            logger.info(f"使用原始消息ID: {channel_msg_id}")

        return channel_msg_id

    def _build_base_comment_link(self, channel_username, channel_id_str, channel_msg_id):
        """构建基础评论区链接"""
        if channel_username:
            link = f"https://t.me/{channel_username}/{channel_msg_id}?comment=1"
            logger.info(f"构建公开频道评论区链接: {link}")
        else:
            link = f"https://t.me/c/{channel_id_str}/{channel_msg_id}?comment=1"
            logger.info(f"构建私有频道评论区链接: {link}")
        return link

    async def _refine_comment_link(
        self, client, linked_group, linked_group_id, context,
        comment_link, channel_username, channel_id_str, channel_msg_id, event,
    ):
        """尝试精确匹配群组消息以优化评论区链接"""
        try:
            logger.info(f"尝试使用用户客户端获取群组 {linked_group_id} 的消息")
            group_messages = await client.get_messages(linked_group, limit=5)
            logger.info(f"成功获取关联群组 {linked_group_id} 的 {len(group_messages)} 条消息")

            matched_msg = self._find_matching_message(group_messages, context, event)

            if matched_msg:
                group_msg_id = matched_msg.id
                if channel_username:
                    comment_link = f"https://t.me/{channel_username}/{channel_msg_id}?comment={group_msg_id}"
                else:
                    comment_link = f"https://t.me/c/{channel_id_str}/{channel_msg_id}?comment={group_msg_id}"
                logger.info(f"更新为精确评论区链接: {comment_link}")
        except Exception as e:
            logger.warning(f"获取群组消息失败，可能是因为未加入群组: {str(e)}")
            logger.info("将使用基本评论区链接")

        return comment_link

    def _find_matching_message(self, group_messages, context, event):
        """从群组消息中查找匹配的消息（内容→相似度→时间→最新）"""
        matched_msg = None
        original_message = context.original_message_text

        # 1. 完全匹配内容
        if original_message:
            logger.info(f"尝试查找内容完全匹配的消息，原始内容长度: {len(original_message)}")
            for msg in group_messages:
                if hasattr(msg, 'message') and msg.message and msg.message == original_message:
                    matched_msg = msg
                    logger.info(f"找到完全匹配消息: 群组消息ID {msg.id}")
                    break

        # 2. 前20字符相似度匹配
        if not matched_msg and original_message and len(original_message) > 20:
            message_start = original_message[:20]
            logger.info(f"尝试对前20字符进行相似度匹配: '{message_start}'")
            for msg in group_messages:
                if hasattr(msg, 'message') and msg.message and len(msg.message) > 20:
                    msg_start = msg.message[:20]
                    similarity = SequenceMatcher(None, message_start, msg_start).ratio()
                    if similarity > 0.75:
                        matched_msg = msg
                        logger.info(f"找到相似度匹配消息: 群组消息ID {msg.id}, 前20字符相似度: {similarity}")
                        break

        # 3. 基于时间匹配
        if not matched_msg and hasattr(event.message, 'date'):
            message_time = event.message.date
            logger.info(f"尝试基于时间匹配，原消息时间: {message_time}")
            time_window = 1
            for msg in group_messages:
                if hasattr(msg, 'date'):
                    time_diff = abs((msg.date - message_time).total_seconds())
                    if time_diff < time_window * 60:
                        matched_msg = msg
                        logger.info(f"找到时间接近的消息: 群组消息ID {msg.id}, 时间差: {time_diff}秒")
                        break

        # 4. 使用最新消息
        if not matched_msg:
            logger.info("未找到匹配消息，尝试使用最新消息")
            if group_messages:
                matched_msg = group_messages[0]
                logger.info(f"使用最新消息: 群组消息ID {matched_msg.id}")

        return matched_msg

    def _add_comment_button(self, context, comment_link):
        """将评论区按钮添加到context中"""
        if not comment_link:
            logger.warning("未能添加任何按钮")
            return

        comment_button = Button.url("💬 查看评论区", comment_link)
        if not context.buttons:
            context.buttons = [[comment_button]]
        else:
            context.buttons.insert(0, [comment_button])

        logger.info(f"为消息添加了评论区按钮，链接: {comment_link}")
