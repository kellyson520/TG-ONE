"""
Telegram API 优化工具模块
提供高效的API调用方法来替代传统的低效实现
"""

import secrets

import asyncio
import logging
import time
from telethon.tl.functions.messages import (
    ForwardMessagesRequest,
    GetMessagesRequest,
    SearchRequest,
)
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import (
    InputDocumentFileLocation,
    InputMessagesFilterDocument,
    InputMessagesFilterEmpty,
    InputMessagesFilterMusic,
    InputMessagesFilterPhotos,
    InputMessagesFilterVideo,
    InputMessagesFilterVoice,
    Message,
)
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class TelegramAPIOptimizer:
    """Telegram API 优化器"""

    def __init__(self):
        self._search_cache = {}  # 搜索结果缓存
        self._media_info_cache = {}  # 媒体信息缓存
        self._cache_ttl = 300  # 缓存5分钟

    async def search_messages_by_keyword(
        self,
        client,
        chat_id: Union[int, str],
        keyword: str,
        limit: int = 100,
        offset_id: int = 0,
        min_date=None,
        max_date=None,
    ) -> List[Message]:
        """
        使用官方搜索API按关键词搜索消息

        Args:
            client: Telegram客户端
            chat_id: 聊天ID
            keyword: 关键词
            limit: 搜索限制
            offset_id: 偏移ID
            min_date: 最小日期
            max_date: 最大日期

        Returns:
            List[Message]: 匹配的消息列表
        """
        try:
            # 检查缓存
            cache_key = f"search:{chat_id}:{keyword}:{limit}:{offset_id}"
            if cache_key in self._search_cache:
                cache_data, timestamp = self._search_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    logger.debug(f"使用缓存的搜索结果: {keyword}")
                    return cache_data

            logger.info(f"使用官方搜索API搜索关键词: {keyword} (聊天: {chat_id})")

            result = await client(
                SearchRequest(
                    peer=chat_id,
                    q=keyword,
                    filter=InputMessagesFilterEmpty(),
                    min_date=min_date,
                    max_date=max_date,
                    offset_id=offset_id,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )

            messages = result.messages if hasattr(result, "messages") else []

            # 更新缓存
            self._search_cache[cache_key] = (messages, time.time())

            logger.info(f"搜索完成: 找到 {len(messages)} 条消息")
            return messages

        except Exception as e:
            logger.error(f"API搜索失败: {str(e)}")
            return []

    async def search_media_messages(
        self,
        client,
        chat_id: Union[int, str],
        media_type: str = "all",
        limit: int = 100,
        offset_id: int = 0,
    ) -> List[Message]:
        """
        使用官方API按媒体类型搜索消息

        Args:
            client: Telegram客户端
            chat_id: 聊天ID
            media_type: 媒体类型 ("photos", "videos", "documents", "music", "voice", "all")
            limit: 搜索限制
            offset_id: 偏移ID

        Returns:
            List[Message]: 匹配的消息列表
        """
        try:
            # 选择过滤器
            filter_map = {
                "photos": InputMessagesFilterPhotos(),
                "videos": InputMessagesFilterVideo(),
                "documents": InputMessagesFilterDocument(),
                "music": InputMessagesFilterMusic(),
                "voice": InputMessagesFilterVoice(),
                "all": InputMessagesFilterEmpty(),
            }

            filter_type = filter_map.get(media_type, InputMessagesFilterEmpty())

            logger.info(f"使用官方API搜索媒体类型: {media_type} (聊天: {chat_id})")

            result = await client(
                SearchRequest(
                    peer=chat_id,
                    q="",
                    filter=filter_type,
                    min_date=None,
                    max_date=None,
                    offset_id=offset_id,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )

            messages = result.messages if hasattr(result, "messages") else []
            logger.info(f"媒体搜索完成: 找到 {len(messages)} 条 {media_type} 消息")
            return messages

        except Exception as e:
            logger.error(f"媒体搜索失败: {str(e)}")
            return []

    async def get_media_info_fast(
        self, client, document, sample_size: int = 1024
    ) -> Dict[str, Any]:
        """
        快速获取媒体文件信息（仅下载头部）

        Args:
            client: Telegram客户端
            document: 文档对象
            sample_size: 采样大小（字节）

        Returns:
            Dict[str, Any]: 媒体信息
        """
        try:
            if not document:
                return {}

            # 检查缓存
            cache_key = f"media:{document.id}:{document.access_hash}"
            if cache_key in self._media_info_cache:
                cache_data, timestamp = self._media_info_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    return cache_data

            # 从文档属性获取基本信息
            info = {
                "id": document.id,
                "size": document.size,
                "mime_type": getattr(document, "mime_type", ""),
                "dc_id": getattr(document, "dc_id", 0),
                "date": getattr(document, "date", None),
                "file_name": None,
                "duration": None,
                "width": None,
                "height": None,
                "has_sample": False,
            }

            # 解析属性
            for attr in document.attributes or []:
                attr_name = attr.__class__.__name__
                if attr_name == "DocumentAttributeFilename":
                    info["file_name"] = getattr(attr, "file_name", None)
                elif attr_name == "DocumentAttributeVideo":
                    info["duration"] = getattr(attr, "duration", None)
                    info["width"] = getattr(attr, "w", None)
                    info["height"] = getattr(attr, "h", None)
                elif attr_name == "DocumentAttributeAudio":
                    info["duration"] = getattr(attr, "duration", None)

            # 如果需要更详细信息且文件不太大，获取文件头部
            if document.size < 10 * 1024 * 1024:  # 小于10MB才采样
                try:
                    file_location = InputDocumentFileLocation(
                        id=document.id,
                        access_hash=document.access_hash,
                        file_reference=document.file_reference,
                        thumb_size="",
                    )

                    file_sample = await client(
                        GetFileRequest(
                            location=file_location, offset=0, limit=sample_size
                        )
                    )

                    if file_sample and hasattr(file_sample, "bytes"):
                        info["has_sample"] = True
                        info["sample_size"] = len(file_sample.bytes)

                        # 基于文件头部进一步分析文件类型
                        header = file_sample.bytes[:16]
                        info["file_header"] = header.hex() if header else ""

                except Exception as sample_error:
                    logger.debug(f"获取文件样本失败: {sample_error}")

            # 更新缓存
            self._media_info_cache[cache_key] = (info, time.time())

            logger.debug(
                f"快速获取媒体信息: {info['file_name']} ({info['size']} bytes)"
            )
            return info

        except Exception as e:
            logger.error(f"快速获取媒体信息失败: {str(e)}")
            return {}

    async def forward_messages_batch(
        self,
        client,
        from_peer: Union[int, str],
        to_peer: Union[int, str],
        message_ids: List[int],
        silent: bool = False,
        background: bool = False,
        with_my_score: bool = True,
    ) -> Any:
        """
        批量转发消息

        Args:
            client: Telegram客户端
            from_peer: 源聊天
            to_peer: 目标聊天
            message_ids: 消息ID列表
            silent: 静默发送
            background: 后台发送
            with_my_score: 带分数

        Returns:
            转发结果
        """
        try:
            if not message_ids:
                return None

            # 生成随机ID - 确保在有符号64位整数范围内
            # Telegram API要求random_id为有符号64位整数：-2^63 到 2^63-1
            random_ids = []
            for _ in message_ids:
                # 生成范围在 0 到 2^63-1 的随机数
                random_id = secrets.randbits(63)
                random_ids.append(random_id)

            logger.info(f"批量转发 {len(message_ids)} 条消息: {from_peer} → {to_peer}")

            result = await client(
                ForwardMessagesRequest(
                    from_peer=from_peer,
                    to_peer=to_peer,
                    id=message_ids,
                    silent=silent,
                    background=background,
                    with_my_score=with_my_score,
                    random_id=random_ids,
                )
            )

            logger.info(f"批量转发完成: {len(message_ids)} 条消息")
            return result

        except Exception as e:
            logger.error(f"批量转发失败: {str(e)}")
            raise

    async def get_messages_batch(
        self, client, chat_id: Union[int, str], message_ids: List[int]
    ) -> List[Message]:
        """
        批量获取消息

        Args:
            client: Telegram客户端
            chat_id: 聊天ID
            message_ids: 消息ID列表

        Returns:
            List[Message]: 消息列表
        """
        try:
            if not message_ids:
                return []

            logger.debug(f"批量获取 {len(message_ids)} 条消息")

            result = await client(GetMessagesRequest(id=message_ids))
            messages = result.messages if hasattr(result, "messages") else []

            logger.debug(f"批量获取完成: {len(messages)} 条消息")
            return messages

        except Exception as e:
            logger.error(f"批量获取消息失败: {str(e)}")
            return []

    def clear_cache(self):
        """清理缓存"""
        self._search_cache.clear()
        self._media_info_cache.clear()
        logger.info("API优化器缓存已清理")

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            "search_cache_size": len(self._search_cache),
            "media_cache_size": len(self._media_info_cache),
        }


# 全局实例
api_optimizer = TelegramAPIOptimizer()
