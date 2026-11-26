"""
增强搜索系统
支持分页、筛选、排序和缓存的统一搜索功能
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

import asyncio
import json
import time
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import SearchRequest as MessagesSearchRequest
from telethon.tl.types import (
    Channel,
)
from telethon.tl.types import Chat as TelegramChat


from typing import Any, Dict, List, Optional

from models.models import Chat, ForwardRule
from sqlalchemy import select
from core.db_factory import AsyncSessionManager
from core.logging import get_logger

logger = get_logger(__name__)


class SearchType(Enum):
    """搜索类型枚举"""

    ALL = "all"  # 全部
    BOUND_CHATS = "bound"  # 已绑定群组
    PUBLIC_CHATS = "public"  # 公开群组
    MESSAGES = "messages"  # 消息
    VIDEOS = "videos"  # 视频
    IMAGES = "images"  # 图片
    FILES = "files"  # 文件
    LINKS = "links"  # 链接
    CHANNELS = "channels"  # 频道
    GROUPS = "groups"  # 群组


class SortBy(Enum):
    """排序方式枚举"""

    TIME_DESC = "time_desc"  # 时间倒序（最新）
    TIME_ASC = "time_asc"  # 时间正序（最旧）
    SIZE_DESC = "size_desc"  # 大小倒序（最大）
    SIZE_ASC = "size_asc"  # 大小正序（最小）
    RELEVANCE = "relevance"  # 相关性
    MEMBERS = "members"  # 成员数量
    ACTIVITY = "activity"  # 活跃度


@dataclass
class SearchFilter:
    """搜索筛选器"""

    search_type: SearchType = SearchType.ALL
    sort_by: SortBy = SortBy.TIME_DESC
    chat_types: Optional[List[str]] = None  # ['channel', 'group', 'supergroup']
    media_types: Optional[List[str]] = None  # ['photo', 'video', 'document']
    min_size: Optional[int] = None  # 最小文件大小(KB)
    max_size: Optional[int] = None  # 最大文件大小(KB)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.chat_types is None:
            self.chat_types = []
        if self.media_types is None:
            self.media_types = []


@dataclass
class SearchResult:
    """搜索结果项"""

    id: str
    title: str
    description: str
    type: str
    subtype: str = ""
    size: int = 0  # 文件大小(字节)
    members: int = 0  # 成员数
    activity_score: float = 0.0  # 活跃度评分
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    link: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchResponse:
    """搜索响应"""

    results: List[SearchResult]
    total_count: int
    current_page: int
    total_pages: int
    per_page: int
    query: str
    filters: SearchFilter
    search_time: float
    cached: bool = False


class SearchCache:
    """搜索缓存管理器"""

    def __init__(self, ttl_hours: int = 24) -> None:
        self._cache: Dict[str, Dict] = {}
        self._ttl_hours = ttl_hours

    def _get_cache_key(self, query: str, filters: SearchFilter, page: int) -> str:
        """生成缓存键"""
        filter_dict = asdict(filters)
        # 移除None值以减少键长度
        filter_dict = {k: v for k, v in filter_dict.items() if v is not None}

        key_data = {
            "query": query.lower().strip(),
            "filters": filter_dict,
            "page": page,
        }
        return json.dumps(key_data, sort_keys=True, default=str)

    def get(
        self, query: str, filters: SearchFilter, page: int
    ) -> Optional[SearchResponse]:
        """获取缓存的搜索结果"""
        cache_key = self._get_cache_key(query, filters, page)

        if cache_key in self._cache:
            cache_data = self._cache[cache_key]

            # 检查是否过期
            created_time = cache_data["created_at"]
            if time.time() - created_time < self._ttl_hours * 3600:
                logger.debug(f"返回缓存的搜索结果: {query}")
                try:
                    # 反序列化datetime对象
                    response_data = cache_data["data"].copy()
                    self._deserialize_datetime_objects(response_data)

                    result = SearchResponse(**response_data)
                    result.cached = True
                    return result
                except Exception as e:
                    logger.warning(f"反序列化缓存失败: {e}")
                    # 删除损坏的缓存
                    del self._cache[cache_key]
            else:
                # 清理过期缓存
                del self._cache[cache_key]

        return None

    def set(
        self, query: str, filters: SearchFilter, page: int, response: SearchResponse
    ) -> None:
        """设置搜索结果缓存"""
        cache_key = self._get_cache_key(query, filters, page)

        # 深拷贝响应对象以避免序列化问题
        try:
            response_dict = asdict(response)
            # 处理datetime对象的序列化
            self._serialize_datetime_objects(response_dict)

            self._cache[cache_key] = {"data": response_dict, "created_at": time.time()}

            # 清理过期缓存（简单策略：每100次写入清理一次）
            if len(self._cache) % 100 == 0:
                self._cleanup_expired()

            logger.debug(f"缓存搜索结果: {query}")
        except Exception as e:
            logger.warning(f"缓存搜索结果失败: {e}")

    def _serialize_datetime_objects(self, obj: Any) -> None:
        """递归处理字典中的datetime对象"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, datetime):
                    obj[key] = value.isoformat()
                elif isinstance(value, (dict, list)):
                    self._serialize_datetime_objects(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, datetime):
                    obj[i] = item.isoformat()
                elif isinstance(item, (dict, list)):
                    self._serialize_datetime_objects(item)

    def _deserialize_datetime_objects(self, obj: Any, path: str = "") -> None:
        """递归处理字典中的datetime字符串，转换回datetime对象"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                child_path = f"{path}.{key}" if path else str(key)
                if isinstance(value, str) and self._is_datetime_string(value):
                    try:
                        obj[key] = datetime.fromisoformat(value)
                    except ValueError as e:
                        logger.warning(
                            "搜索缓存时间反序列化失败: path=%s, value=%r, error=%s",
                            child_path,
                            value,
                            e,
                        )
                elif isinstance(value, (dict, list)):
                    self._deserialize_datetime_objects(value, child_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                child_path = f"{path}[{i}]" if path else f"[{i}]"
                if isinstance(item, str) and self._is_datetime_string(item):
                    try:
                        obj[i] = datetime.fromisoformat(item)
                    except ValueError as e:
                        logger.warning(
                            "搜索缓存时间反序列化失败: path=%s, value=%r, error=%s",
                            child_path,
                            item,
                            e,
                        )
                elif isinstance(item, (dict, list)):
                    self._deserialize_datetime_objects(item, child_path)

    def _is_datetime_string(self, value: str) -> bool:
        """检查字符串是否是datetime格式"""
        if not isinstance(value, str) or len(value) < 10:
            return False
        # 简单检查：以数字开头，包含T或空格，符合ISO格式
        return (
            value[0].isdigit()
            and ("T" in value or " " in value)
            and value.count("-") >= 2
        )

    def _cleanup_expired(self) -> None:
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []

        for key, data in self._cache.items():
            if current_time - data["created_at"] >= self._ttl_hours * 3600:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存项")


class EnhancedSearchSystem:
    """增强搜索系统"""

    def __init__(self, user_client: Any = None) -> None:
        self.user_client = user_client
        self.cache = SearchCache()
        self.per_page = 10

    async def search(
        self, query: str, filters: Optional[SearchFilter] = None, page: int = 1
    ) -> SearchResponse:
        """执行搜索"""
        if filters is None:
            filters = SearchFilter()

        # 检查缓存
        cached_result = self.cache.get(query, filters, page)
        if cached_result:
            return cached_result

        start_time = time.time()

        try:
            # 根据搜索类型执行不同的搜索逻辑
            if filters.search_type == SearchType.BOUND_CHATS:
                results = await self._search_bound_chats(query, filters)
            elif filters.search_type == SearchType.PUBLIC_CHATS:
                results = await self._search_public_chats(query, filters)
            elif filters.search_type == SearchType.MESSAGES:
                results = await self._search_messages(query, filters)
            elif filters.search_type in [
                SearchType.VIDEOS,
                SearchType.IMAGES,
                SearchType.FILES,
            ]:
                results = await self._search_media(query, filters)
            else:  # SearchType.ALL
                results = await self._search_all(query, filters)

            # 排序
            results = self._sort_results(results, filters.sort_by, query)

            # 分页
            total_count = len(results)
            total_pages = (total_count + self.per_page - 1) // self.per_page
            start_idx = (page - 1) * self.per_page
            end_idx = start_idx + self.per_page
            page_results = results[start_idx:end_idx]

            search_time = time.time() - start_time

            response = SearchResponse(
                results=page_results,
                total_count=total_count,
                current_page=page,
                total_pages=total_pages,
                per_page=self.per_page,
                query=query,
                filters=filters,
                search_time=search_time,
            )

            # 缓存结果
            self.cache.set(query, filters, page, response)

            return response

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return SearchResponse(
                results=[],
                total_count=0,
                current_page=page,
                total_pages=0,
                per_page=self.per_page,
                query=query,
                filters=filters,
                search_time=time.time() - start_time,
            )

    async def _search_bound_chats(
        self, query: str, filters: SearchFilter
    ) -> List[SearchResult]:
        """搜索已绑定的聊天"""
        async with AsyncSessionManager(readonly=True) as session:
            stmt = select(Chat)

            if query.strip():
                stmt = stmt.filter(
                    (Chat.name.ilike(f"%{query}%"))
                    | (Chat.telegram_chat_id.ilike(f"%{query}%"))
                    | (Chat.chat_type.ilike(f"%{query}%"))
                )

            # 类型筛选
            if filters.chat_types:
                stmt = stmt.filter(Chat.chat_type.in_(filters.chat_types))

            result = await session.execute(stmt)
            chats = result.scalars().all()
            results = []

            for chat in chats:
                # 计算规则数量作为活跃度
                rule_count_result = await session.execute(
                    select(ForwardRule).filter(
                        (ForwardRule.source_chat_id == chat.id)
                        | (ForwardRule.target_chat_id == chat.id)
                    )
                )
                rule_count = len(rule_count_result.scalars().all())

                result_item = SearchResult(
                    id=f"bound_chat_{chat.id}",
                    title=chat.name or "未命名",
                    description=f"ID: {chat.telegram_chat_id} | 类型: {chat.chat_type or '未知'}",
                    type="bound_chat",
                    subtype=chat.chat_type or "unknown",
                    members=chat.member_count or 0,
                    activity_score=float(rule_count),
                    telegram_id=(
                        int(chat.telegram_chat_id)
                        if chat.telegram_chat_id.lstrip("-").isdigit()
                        else None
                    ),
                    created_at=(
                        datetime.fromisoformat(chat.created_at)
                        if chat.created_at
                        else None
                    ),
                    metadata={
                        "rule_count": rule_count,
                        "is_active": chat.is_active,
                        "description": chat.description,
                    },
                )
                results.append(result_item)

            return results

    async def _search_public_chats(
        self, query: str, filters: SearchFilter
    ) -> List[SearchResult]:
        """搜索公开聊天"""
        if not self.user_client or not query.strip():
            return []

        try:
            # 使用Telegram官方API搜索
            result = await self.user_client(SearchRequest(q=query, limit=50))

            search_results = []
            for chat in result.chats:
                if isinstance(chat, (Channel, TelegramChat)):
                    # 类型筛选
                    chat_type = self._get_chat_type(chat)
                    if filters.chat_types and chat_type not in filters.chat_types:
                        continue

                    # 跳过私人聊天
                    if not (
                        hasattr(chat, "broadcast")
                        or hasattr(chat, "megagroup")
                        or getattr(chat, "participants_count", 0) > 1
                    ):
                        continue

                    result_item = SearchResult(
                        id=f"public_chat_{chat.id}",
                        title=chat.title,
                        description=getattr(chat, "about", "") or "",
                        type="public_chat",
                        subtype=chat_type,
                        members=getattr(chat, "participants_count", 0),
                        activity_score=self._calculate_activity_score(chat),
                        telegram_id=chat.id,
                        username=getattr(chat, "username", None),
                        link=(
                            f"https://t.me/{chat.username}"
                            if getattr(chat, "username", None)
                            else None
                        ),
                        created_at=getattr(chat, "date", None),
                        metadata={
                            "verified": getattr(chat, "verified", False),
                            "scam": getattr(chat, "scam", False),
                            "fake": getattr(chat, "fake", False),
                            "restricted": getattr(chat, "restricted", False),
                        },
                    )
                    search_results.append(result_item)

            return search_results

        except Exception as e:
            logger.error(f"搜索公开聊天失败: {e}")
            import traceback

            logger.debug(
                f"搜索公开聊天失败详情: query={query}, error_type={type(e).__name__}, error_trace={traceback.format_exc()}"
            )
            return []

    async def _search_messages(
        self, query: str, filters: SearchFilter
    ) -> List[SearchResult]:
        """搜索消息内容"""
        if not self.user_client or not query.strip():
            return []

        results = []

        try:
            # 从数据库获取已绑定的聊天
            async with AsyncSessionManager(readonly=True) as session:
                result = await session.execute(
                    select(Chat).filter(Chat.is_active == True)
                )
                bound_chats = result.scalars().all()

            # 限制搜索的聊天数量，避免太耗时
            max_chats_to_search = 10
            search_count = 0

            for chat_record in bound_chats:
                if search_count >= max_chats_to_search:
                    break

                try:
                    chat_id = int(chat_record.telegram_chat_id)

                    # 使用 Telethon 的消息搜索功能

                    from telethon.tl.types import (
                        MessagesFilter,
                    )

                    # 获取聊天实体
                    try:
                        chat_entity = await self.user_client.get_entity(chat_id)
                    except Exception as e:
                        logger.warning(f"无法获取聊天实体 {chat_id}: {e}")
                        continue

                    # 搜索消息
                    search_results = await self.user_client(
                        MessagesSearchRequest(
                            peer=chat_entity,
                            q=query,
                            filter=MessagesFilter(),  # 默认搜索所有消息
                            min_date=None,
                            max_date=None,
                            offset_id=0,
                            add_offset=0,
                            limit=20,  # 每个聊天最多搜索20条消息
                            max_id=0,
                            min_id=0,
                            hash=0,
                        )
                    )

                    # 处理搜索结果
                    for message in search_results.messages:
                        if hasattr(message, "message") and message.message:
                            # 应用时间筛选
                            if filters.date_from and message.date < filters.date_from:
                                continue
                            if filters.date_to and message.date > filters.date_to:
                                continue

                            # 计算相关性评分
                            relevance_score = self._calculate_message_relevance(
                                query, message.message
                            )

                            result_item = SearchResult(
                                id=f"message_{chat_id}_{message.id}",
                                title=f"💬 {chat_record.name or '未知聊天'}",
                                description=self._truncate_message(
                                    message.message, 100
                                ),
                                type="message",
                                subtype="text",
                                telegram_id=message.id,
                                created_at=message.date,
                                activity_score=relevance_score,
                                metadata={
                                    "chat_id": chat_id,
                                    "chat_name": chat_record.name,
                                    "message_text": message.message,
                                    "sender_id": (
                                        getattr(message.from_id, "user_id", None)
                                        if message.from_id
                                        else None
                                    ),
                                    "views": getattr(message, "views", 0),
                                    "forwards": getattr(message, "forwards", 0),
                                },
                            )
                            results.append(result_item)

                    search_count += 1

                    # 添加小延迟避免触发 API 限制
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.warning(
                        f"搜索聊天 {chat_record.name} ({chat_id}) 的消息失败: {e}"
                    )
                    continue

            logger.info(f"消息搜索完成，找到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"搜索消息时发生错误: {e}")
            return results

    async def _search_media(
        self, query: str, filters: SearchFilter
    ) -> List[SearchResult]:
        """搜索媒体文件"""
        if not self.user_client:
            return []

        results = []

        try:
            # 从数据库获取已绑定的聊天
            async with AsyncSessionManager(readonly=True) as session:
                result = await session.execute(
                    select(Chat).filter(Chat.is_active == True)
                )
                bound_chats = result.scalars().all()

            # 限制搜索的聊天数量
            max_chats_to_search = 5  # 媒体搜索更耗时，减少聊天数量
            search_count = 0

            for chat_record in bound_chats:
                if search_count >= max_chats_to_search:
                    break

                try:
                    chat_id = int(chat_record.telegram_chat_id)
                    chat_entity = await self.user_client.get_entity(chat_id)

                    # 根据筛选类型确定搜索的媒体类型
                    media_filters = []
                    if filters.search_type == SearchType.VIDEOS:
                        from telethon.tl.types import InputMessagesFilterVideo

                        media_filters = [InputMessagesFilterVideo()]
                    elif filters.search_type == SearchType.IMAGES:
                        from telethon.tl.types import InputMessagesFilterPhotos

                        media_filters = [InputMessagesFilterPhotos()]
                    elif filters.search_type == SearchType.FILES:
                        from telethon.tl.types import InputMessagesFilterDocument

                        media_filters = [InputMessagesFilterDocument()]
                    else:
                        # 搜索所有媒体类型
                        from telethon.tl.types import (
                            InputMessagesFilterDocument,
                            InputMessagesFilterPhotos,
                            InputMessagesFilterVideo,
                        )

                        media_filters = [
                            InputMessagesFilterVideo(),
                            InputMessagesFilterPhotos(),
                            InputMessagesFilterDocument(),
                        ]

                    # 对每种媒体类型进行搜索
                    for media_filter in media_filters:
                        try:


                            search_results = await self.user_client(
                                MessagesSearchRequest(
                                    peer=chat_entity,
                                    q=query,
                                    filter=media_filter,
                                    min_date=None,
                                    max_date=None,
                                    offset_id=0,
                                    add_offset=0,
                                    limit=10,  # 每种类型搜索10条
                                    max_id=0,
                                    min_id=0,
                                    hash=0,
                                )
                            )

                            # 处理搜索结果
                            for message in search_results.messages:
                                if message.media:
                                    media_info = self._extract_media_info(message)
                                    if media_info:
                                        # 应用大小筛选
                                        if (
                                            filters.min_size
                                            and media_info["size"]
                                            < filters.min_size * 1024
                                        ):
                                            continue
                                        if (
                                            filters.max_size
                                            and media_info["size"]
                                            > filters.max_size * 1024
                                        ):
                                            continue

                                        # 应用时间筛选
                                        if (
                                            filters.date_from
                                            and message.date < filters.date_from
                                        ):
                                            continue
                                        if (
                                            filters.date_to
                                            and message.date > filters.date_to
                                        ):
                                            continue

                                        result_item = SearchResult(
                                            id=f"media_{chat_id}_{message.id}",
                                            title=f"{media_info['emoji']} {media_info['filename']}",
                                            description=f"来源: {chat_record.name} | 大小: {self._format_file_size(media_info['size'])}",
                                            type="media",
                                            subtype=media_info["type"],
                                            size=media_info["size"],
                                            telegram_id=message.id,
                                            created_at=message.date,
                                            activity_score=float(
                                                media_info["size"] / (1024 * 1024)
                                            ),  # 以MB为单位的大小作为评分
                                            metadata={
                                                "chat_id": chat_id,
                                                "chat_name": chat_record.name,
                                                "filename": media_info["filename"],
                                                "mime_type": media_info.get(
                                                    "mime_type"
                                                ),
                                                "duration": media_info.get("duration"),
                                                "dimensions": media_info.get(
                                                    "dimensions"
                                                ),
                                            },
                                        )
                                        results.append(result_item)

                            # 延迟避免API限制
                            await asyncio.sleep(0.2)

                        except Exception as e:
                            logger.warning(f"搜索媒体类型失败: {e}")
                            continue

                    search_count += 1

                except Exception as e:
                    logger.warning(f"搜索聊天 {chat_record.name} 的媒体失败: {e}")
                    continue

            logger.info(f"媒体搜索完成，找到 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"搜索媒体时发生错误: {e}")
            return results

    async def _search_all(
        self, query: str, filters: SearchFilter
    ) -> List[SearchResult]:
        """搜索所有内容"""
        all_results = []

        # 并行搜索不同类型的内容
        import asyncio

        tasks = []

        # 绑定的聊天
        tasks.append(self._search_bound_chats(query, filters))

        # 公开聊天
        tasks.append(self._search_public_chats(query, filters))

        # 消息内容（如果有查询词）
        if query.strip():
            tasks.append(self._search_messages(query, filters))

        # 执行所有搜索任务
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"搜索任务失败: {result}")

        except Exception as e:
            logger.error(f"执行搜索任务时发生错误: {e}")

        return all_results

    def _get_chat_type(self, chat: Any) -> str:
        """获取聊天类型"""
        if hasattr(chat, "broadcast") and chat.broadcast:
            return "channel"
        elif hasattr(chat, "megagroup") and chat.megagroup:
            return "supergroup"
        elif isinstance(chat, Channel):
            return "channel"
        else:
            return "group"

    def _calculate_activity_score(self, chat: Any) -> float:
        """计算活跃度评分"""
        score = 0.0

        # 基于成员数
        members = getattr(chat, "participants_count", 0)
        if members > 0:
            score += min(members / 1000, 10.0)  # 最高10分

        # 基于是否认证
        if getattr(chat, "verified", False):
            score += 5.0

        # 基于是否有用户名
        if getattr(chat, "username", None):
            score += 2.0

        return score

    def _sort_results(
        self, results: List[SearchResult], sort_by: SortBy, query: str = ""
    ) -> List[SearchResult]:
        """排序搜索结果"""
        if sort_by == SortBy.TIME_DESC:
            return sorted(
                results, key=lambda x: x.created_at or datetime.min, reverse=True
            )
        elif sort_by == SortBy.TIME_ASC:
            return sorted(results, key=lambda x: x.created_at or datetime.min)
        elif sort_by == SortBy.SIZE_DESC:
            return sorted(results, key=lambda x: x.size, reverse=True)
        elif sort_by == SortBy.SIZE_ASC:
            return sorted(results, key=lambda x: x.size)
        elif sort_by == SortBy.MEMBERS:
            return sorted(results, key=lambda x: x.members, reverse=True)
        elif sort_by == SortBy.ACTIVITY:
            return sorted(results, key=lambda x: x.activity_score, reverse=True)
        else:  # SortBy.RELEVANCE
            # 简单的相关性评分：标题匹配 > 描述匹配 > 活跃度
            def relevance_score(result: SearchResult) -> float:
                score = result.activity_score
                if query:
                    query_lower = query.lower()
                    # 安全的字符串匹配，避免None值错误
                    title = result.title or ""
                    description = result.description or ""
                    if query_lower in title.lower():
                        score += 10.0
                    if query_lower in description.lower():
                        score += 5.0
                return score

            return sorted(results, key=relevance_score, reverse=True)

    def _calculate_message_relevance(self, query: str, message_text: str) -> float:
        """计算消息相关性评分"""
        if not query or not message_text:
            return 0.0

        query_lower = query.lower()
        message_lower = message_text.lower()
        score = 0.0

        # 完全匹配
        if query_lower == message_lower:
            score += 100.0
        # 包含查询词
        elif query_lower in message_lower:
            # 根据位置给分：开头 > 中间 > 结尾
            position = message_lower.find(query_lower)
            max_score = 50.0
            if position == 0:
                score += max_score
            elif position < len(message_lower) * 0.3:
                score += max_score * 0.8
            elif position < len(message_lower) * 0.7:
                score += max_score * 0.5
            else:
                score += max_score * 0.3

        # 查询词分词匹配
        query_words = query_lower.split()
        message_words = message_lower.split()

        matched_words = 0
        for word in query_words:
            if word in message_words:
                matched_words += 1

        if query_words:
            word_match_ratio = matched_words / len(query_words)
            score += word_match_ratio * 20.0

        # 消息长度惩罚（短消息更相关）
        if len(message_text) > 0:
            length_penalty = min(len(message_text) / 1000, 1.0) * 10
            score = max(0, score - length_penalty)

        return score

    def _truncate_message(self, message: str, max_length: int = 100) -> str:
        """截断消息内容"""
        if not message:
            return ""

        if len(message) <= max_length:
            return message

        # 在单词边界截断
        truncated = message[:max_length]
        last_space = truncated.rfind(" ")

        if last_space > max_length * 0.7:  # 如果最后一个空格位置合理
            truncated = truncated[:last_space]

        return truncated + "..."

    def _extract_media_info(self, message: Any) -> Optional[Dict[str, Any]]:
        """提取消息中的媒体信息"""
        if not message.media:
            return None

        media_info = {"filename": "", "size": 0, "type": "unknown", "emoji": "📄"}

        try:
            if hasattr(message.media, "document") and message.media.document:
                doc = message.media.document
                media_info["size"] = doc.size
                media_info["mime_type"] = doc.mime_type

                # 根据MIME类型判断文件类型
                if doc.mime_type:
                    if doc.mime_type.startswith("video/"):
                        media_info["type"] = "video"
                        media_info["emoji"] = "🎬"
                    elif doc.mime_type.startswith("image/"):
                        media_info["type"] = "image"
                        media_info["emoji"] = "🖼️"
                    elif doc.mime_type.startswith("audio/"):
                        media_info["type"] = "audio"
                        media_info["emoji"] = "🎵"
                    else:
                        media_info["type"] = "document"
                        media_info["emoji"] = "📁"
                # 提取文件名
                for attr in doc.attributes:
                    if hasattr(attr, "file_name") and attr.file_name:
                        media_info["filename"] = attr.file_name
                        break
                    elif hasattr(attr, "duration"):
                        media_info["duration"] = attr.duration
                    elif hasattr(attr, "w") and hasattr(attr, "h"):
                        media_info["dimensions"] = f"{attr.w}x{attr.h}"

                # 如果没有文件名，生成一个
                if not media_info["filename"]:
                    file_ext = self._get_extension_from_mime(doc.mime_type)
                    media_info["filename"] = f"文件_{message.id}{file_ext}"

            elif hasattr(message.media, "photo") and message.media.photo:
                # 处理照片
                photo = message.media.photo
                media_info["type"] = "photo"
                media_info["emoji"] = "📷"
                media_info["filename"] = f"照片_{message.id}.jpg"

                # 获取最大尺寸的照片信息
                if hasattr(photo, "sizes") and photo.sizes:
                    largest_size = max(
                        photo.sizes,
                        key=lambda s: (
                            getattr(s, "size", 0) if hasattr(s, "size") else 0
                        ),
                    )
                    if hasattr(largest_size, "size"):
                        media_info["size"] = largest_size.size
                    if hasattr(largest_size, "w") and hasattr(largest_size, "h"):
                        media_info["dimensions"] = f"{largest_size.w}x{largest_size.h}"

            return media_info

        except Exception as e:
            logger.warning(f"提取媒体信息失败: {e}")
            return None

    def _get_extension_from_mime(self, mime_type: str) -> str:
        """根据MIME类型获取文件扩展名"""
        mime_to_ext = {
            "video/mp4": ".mp4",
            "video/avi": ".avi",
            "video/mkv": ".mkv",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/ogg": ".ogg",
            "application/pdf": ".pdf",
            "application/zip": ".zip",
            "text/plain": ".txt",
        }
        return mime_to_ext.get(mime_type, "")

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"


# 全局搜索系统实例
_search_system = None


def get_search_system(user_client: Any = None) -> EnhancedSearchSystem:
    """获取全局搜索系统实例"""
    global _search_system
    if _search_system is None:
        _search_system = EnhancedSearchSystem(user_client)
    elif user_client and _search_system.user_client is None:
        _search_system.user_client = user_client
    return _search_system
