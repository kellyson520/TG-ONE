"""
综合搜索服务
支持本地数据库搜索与 Telegram 远程搜索
"""
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

class SearchType(Enum):
    ALL = "all"
    BOUND_CHATS = "bound"
    PUBLIC_CHATS = "public"
    MESSAGES = "messages"
    VIDEOS = "videos"
    IMAGES = "images"
    FILES = "files"
    LINKS = "links"
    CHANNELS = "channels"
    GROUPS = "groups"

@dataclass
class SearchFilter:
    search_type: SearchType = SearchType.ALL
    chat_types: List[str] = None
    media_types: List[str] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    date_from: Optional[Any] = None
    date_to: Optional[Any] = None

class SearchService:
    def __init__(self, container=None):
        self.container = container
        self._search_system = None

    @property
    def search_system(self):
        if self._search_system is None:
            from core.helpers.search_system import EnhancedSearchSystem
            from core.container import container
            self._search_system = EnhancedSearchSystem(user_client=container.user_client)
        return self._search_system

    async def search(self, query: str, search_type: str = "all", page: int = 1) -> Dict[str, Any]:
        """执行综合搜索"""
        try:
            from core.helpers.search_system import SearchFilter, SearchType as HelperSearchType
            st = HelperSearchType.ALL
            try: st = HelperSearchType(search_type)
            except ValueError: pass
            filters = SearchFilter(search_type=st)
            response = await self.search_system.search(query, filters, page)
            return {
                "success": True,
                "results": [asdict(r) for r in response.results],
                "total_count": response.total_count,
                "current_page": response.current_page,
                "total_pages": response.total_pages,
                "search_time": response.search_time,
                "cached": response.cached
            }
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"success": False, "error": str(e)}

search_service = SearchService()
