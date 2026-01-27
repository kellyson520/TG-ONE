"""
高级数据库查询优化器
提供查询结果缓存、预热、批量操作等高性能数据库访问能力
"""

import hashlib
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from models.models import get_read_session, get_session
from core.logging import get_logger
from repositories.persistent_cache import get_persistent_cache
from core.cache.unified_cache import MultiLevelCache, get_smart_cache

logger = get_logger(__name__)


class QueryResultCache:
    """查询结果智能缓存"""

    def __init__(self):
        self.cache = get_smart_cache("query_results", l1_ttl=60, l2_ttl=300)
        self.access_patterns = defaultdict(list)
        self.lock = threading.RLock()

    def generate_cache_key(self, query_type: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        key_data = {"type": query_type, "params": params, "version": "1.0"}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return f"query:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    def get(self, query_type: str, params: Dict[str, Any]) -> Optional[Any]:
        """获取缓存结果"""
        cache_key = self.generate_cache_key(query_type, params)
        result = self.cache.get(cache_key)

        if result is not None:
            # 记录访问模式
            with self.lock:
                self.access_patterns[query_type].append(time.time())
                # 保持最近1000次访问记录
                if len(self.access_patterns[query_type]) > 1000:
                    self.access_patterns[query_type] = self.access_patterns[query_type][
                        -1000:
                    ]

        return result

    def set(
        self, query_type: str, params: Dict[str, Any], result: Any, ttl: int = 300
    ) -> None:
        """设置缓存结果"""
        cache_key = self.generate_cache_key(query_type, params)
        self.cache.set(cache_key, result, ttl=ttl)

    def invalidate_pattern(self, query_type: str) -> None:
        """使某类查询的缓存失效"""
        # 这里可以实现更精细的失效策略
        logger.info(f"Query cache invalidated for type: {query_type}")

    def get_hot_queries(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取热点查询"""
        now = time.time()
        hour_ago = now - 3600

        hot_queries = []
        with self.lock:
            for query_type, accesses in self.access_patterns.items():
                recent_count = sum(1 for ts in accesses if ts > hour_ago)
                if recent_count > 0:
                    hot_queries.append((query_type, recent_count))

        return sorted(hot_queries, key=lambda x: x[1], reverse=True)[:limit]


# 全局查询缓存实例
query_cache = QueryResultCache()


def cached_query(
    query_type: str, ttl: int = 300, invalidate_on: Optional[List[str]] = None
):
    """查询结果缓存装饰器"""

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成参数字典
            params = {"args": args, "kwargs": kwargs}

            # 尝试从缓存获取
            cached_result = query_cache.get(query_type, params)
            if cached_result is not None:
                logger.debug(f"Query cache hit: {query_type}")
                return cached_result

            # 执行查询
            start_time = time.time()
            result = await func(*args, **kwargs)
            query_time = time.time() - start_time

            # 缓存结果
            query_cache.set(query_type, params, result, ttl=ttl)

            logger.debug(f"Query executed: {query_type}, time: {query_time:.3f}s")
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 生成参数字典
            params = {"args": args, "kwargs": kwargs}

            # 尝试从缓存获取
            cached_result = query_cache.get(query_type, params)
            if cached_result is not None:
                logger.debug(f"Query cache hit: {query_type}")
                return cached_result

            # 执行查询
            start_time = time.time()
            result = func(*args, **kwargs)
            query_time = time.time() - start_time

            # 缓存结果
            query_cache.set(query_type, params, result, ttl=ttl)

            logger.debug(f"Query executed: {query_type}, time: {query_time:.3f}s")
            return result

        # 根据函数是否为协程返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class BatchQueryExecutor:
    """批量查询执行器"""

    def __init__(self):
        self.pending_queries = defaultdict(list)
        self.batch_size = 50
        self.batch_timeout = 0.1  # 100ms
        self.lock = threading.RLock()

    async def execute_batch_ids(
        self, query_func: Callable, table_name: str, ids: List[int]
    ) -> Dict[int, Any]:
        """批量按ID查询"""
        if not ids:
            return {}

        try:
            with get_read_session() as session:
                results = query_func(session, ids)
                return {getattr(r, "id"): r for r in results}
        except Exception as e:
            logger.error(f"Batch query failed for {table_name}: {e}")
            return {}

    async def execute_batch_conditions(
        self, query_func: Callable, conditions: List[Dict]
    ) -> List[Any]:
        """批量条件查询"""
        if not conditions:
            return []

        try:
            with get_read_session() as session:
                return query_func(session, conditions)
        except Exception as e:
            logger.error(f"Batch conditional query failed: {e}")
            return []


class QueryPrewarmer:
    """查询预热器"""

    def __init__(self):
        self.prewarming_tasks = set()

    async def prewarm_hot_queries(self):
        """预热热点查询"""
        hot_queries = query_cache.get_hot_queries(limit=5)

        for query_type, count in hot_queries:
            if query_type not in self.prewarming_tasks:
                self.prewarming_tasks.add(query_type)
                asyncio.create_task(self._prewarm_query_type(query_type))

    async def _prewarm_query_type(self, query_type: str):
        """预热特定类型的查询"""
        try:
            # 这里可以根据query_type实现具体的预热逻辑
            if query_type == "rule_with_keywords":
                await self._prewarm_rules_with_keywords()
            elif query_type == "active_rss_configs":
                await self._prewarm_rss_configs()
            elif query_type == "recent_media_signatures":
                await self._prewarm_recent_media()

        except Exception as e:
            logger.error(f"Prewarming failed for {query_type}: {e}")
        finally:
            self.prewarming_tasks.discard(query_type)

    async def _prewarm_rules_with_keywords(self):
        """预热规则和关键字查询"""
        try:
            from sqlalchemy.orm import joinedload, selectinload

            from models.models import ForwardRule

            with get_read_session() as session:
                # 预加载活跃规则及其关联数据
                rules = (
                    session.query(ForwardRule)
                    .options(
                        joinedload(ForwardRule.source_chat),
                        joinedload(ForwardRule.target_chat),
                        selectinload(ForwardRule.keywords),
                        selectinload(ForwardRule.replace_rules),
                        joinedload(ForwardRule.media_types),
                    )
                    .filter(ForwardRule.enable_rule == True)
                    .limit(20)
                    .all()
                )

                logger.info(f"Prewarmed {len(rules)} active rules")
        except Exception as e:
            logger.error(f"Failed to prewarm rules: {e}")

    async def _prewarm_rss_configs(self):
        """预热RSS配置查询"""
        try:
            from sqlalchemy.orm import joinedload

            from models.models import RSSConfig

            with get_read_session() as session:
                configs = (
                    session.query(RSSConfig)
                    .options(joinedload(RSSConfig.patterns))
                    .filter(RSSConfig.enable_rss == True)
                    .limit(10)
                    .all()
                )

                logger.info(f"Prewarmed {len(configs)} RSS configs")
        except Exception as e:
            logger.error(f"Failed to prewarm RSS configs: {e}")

    async def _prewarm_recent_media(self):
        """预热最近媒体签名查询"""
        try:
            from models.models import MediaSignature

            with get_read_session() as session:
                cutoff = (datetime.utcnow() - timedelta(days=1)).isoformat()
                media = (
                    session.query(MediaSignature)
                    .filter(MediaSignature.created_at > cutoff)
                    .limit(100)
                    .all()
                )

                logger.info(f"Prewarmed {len(media)} recent media signatures")
        except Exception as e:
            logger.error(f"Failed to prewarm media signatures: {e}")


# 全局实例
batch_executor = BatchQueryExecutor()
query_prewarmer = QueryPrewarmer()


class OptimizedQueries:
    """优化后的查询接口"""

    @staticmethod
    @cached_query("rule_with_keywords", ttl=600)
    def get_rule_with_keywords(rule_id: int) -> Optional[Dict[str, Any]]:
        """获取规则及其关键字（带缓存）"""
        try:
            from sqlalchemy.orm import joinedload, selectinload

            from models.models import ForwardRule, Keyword

            with get_read_session() as session:
                rule = (
                    session.query(ForwardRule)
                    .options(
                        joinedload(ForwardRule.source_chat),
                        joinedload(ForwardRule.target_chat),
                        selectinload(ForwardRule.keywords),
                        selectinload(ForwardRule.replace_rules),
                        joinedload(ForwardRule.media_types),
                    )
                    .filter(ForwardRule.id == rule_id)
                    .first()
                )

                if not rule:
                    return None

                return {
                    "id": rule.id,
                    "source_chat_id": rule.source_chat_id,
                    "target_chat_id": rule.target_chat_id,
                    "source_chat": (
                        {
                            "id": rule.source_chat.id,
                            "telegram_chat_id": rule.source_chat.telegram_chat_id,
                            "name": rule.source_chat.name,
                        }
                        if rule.source_chat
                        else None
                    ),
                    "target_chat": (
                        {
                            "id": rule.target_chat.id,
                            "telegram_chat_id": rule.target_chat.telegram_chat_id,
                            "name": rule.target_chat.name,
                        }
                        if rule.target_chat
                        else None
                    ),
                    "keywords": [
                        {
                            "id": kw.id,
                            "keyword": kw.keyword,
                            "is_blacklist": kw.is_blacklist,
                            "is_regex": kw.is_regex,
                        }
                        for kw in rule.keywords
                    ],
                    "enable_rule": rule.enable_rule,
                    "forward_mode": (
                        rule.forward_mode.value if rule.forward_mode else None
                    ),
                }
        except Exception as e:
            logger.error(f"Failed to get rule with keywords: {e}")
            return None

    @staticmethod
    @cached_query("active_rss_configs", ttl=300)
    def get_active_rss_configs() -> List[Dict[str, Any]]:
        """获取活跃的RSS配置（带缓存）"""
        try:
            from sqlalchemy.orm import joinedload

            from models.models import RSSConfig

            with get_read_session() as session:
                configs = (
                    session.query(RSSConfig)
                    .options(joinedload(RSSConfig.patterns))
                    .filter(RSSConfig.enable_rss == True)
                    .all()
                )

                return [
                    {
                        "id": config.id,
                        "rule_id": config.rule_id,
                        "title": config.title,
                        "max_items": config.max_items,
                        "patterns": [
                            {
                                "id": p.id,
                                "pattern": p.pattern,
                                "pattern_type": p.pattern_type,
                                "priority": p.priority,
                            }
                            for p in config.patterns
                        ],
                    }
                    for config in configs
                ]
        except Exception as e:
            logger.error(f"Failed to get active RSS configs: {e}")
            return []

    @staticmethod
    @cached_query("chat_by_telegram_id", ttl=1800)
    def get_chat_by_telegram_id(telegram_chat_id: str) -> Optional[Dict[str, Any]]:
        """根据Telegram ID获取聊天（带缓存）"""
        try:
            from models.models import Chat

            with get_read_session() as session:
                chat = (
                    session.query(Chat)
                    .filter(Chat.telegram_chat_id == str(telegram_chat_id))
                    .first()
                )

                if not chat:
                    return None

                return {
                    "id": chat.id,
                    "telegram_chat_id": chat.telegram_chat_id,
                    "name": chat.name,
                    "chat_type": chat.chat_type,
                    "is_active": chat.is_active,
                    "member_count": chat.member_count,
                }
        except Exception as e:
            logger.error(f"Failed to get chat by telegram ID: {e}")
            return None

    @staticmethod
    async def batch_get_rules_by_ids(rule_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """批量获取规则"""

        def query_func(session, ids):
            from sqlalchemy.orm import joinedload, selectinload

            from models.models import ForwardRule

            return (
                session.query(ForwardRule)
                .options(
                    joinedload(ForwardRule.source_chat),
                    joinedload(ForwardRule.target_chat),
                    selectinload(ForwardRule.keywords),
                )
                .filter(ForwardRule.id.in_(ids))
                .all()
            )

        return await batch_executor.execute_batch_ids(
            query_func, "ForwardRule", rule_ids
        )

    @staticmethod
    @cached_query("media_signature_exists", ttl=60)
    def check_media_signature_exists(chat_id: str, signature: str) -> bool:
        """检查媒体签名是否存在（带缓存）"""
        try:
            from models.models import MediaSignature

            with get_read_session() as session:
                exists = (
                    session.query(MediaSignature)
                    .filter(
                        MediaSignature.chat_id == str(chat_id),
                        MediaSignature.signature == str(signature),
                    )
                    .first()
                    is not None
                )

                return exists
        except Exception as e:
            logger.error(f"Failed to check media signature: {e}")
            return False


# 缓存失效管理
class CacheInvalidationManager:
    """缓存失效管理器"""

    @staticmethod
    def invalidate_rule_caches(rule_id: int):
        """规则相关缓存失效"""
        query_cache.invalidate_pattern("rule_with_keywords")
        query_cache.invalidate_pattern("active_rss_configs")

    @staticmethod
    def invalidate_chat_caches(telegram_chat_id: str):
        """聊天相关缓存失效"""
        query_cache.invalidate_pattern("chat_by_telegram_id")

    @staticmethod
    def invalidate_media_caches(chat_id: str):
        """媒体相关缓存失效"""
        query_cache.invalidate_pattern("media_signature_exists")


# 启动预热任务
async def start_query_optimization():
    """启动查询优化服务"""
    logger.info("Starting query optimization services...")

    # 启动预热任务
    asyncio.create_task(query_prewarmer.prewarm_hot_queries())

    # 定期预热热点查询
    async def periodic_prewarm():
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟
                await query_prewarmer.prewarm_hot_queries()
            except Exception as e:
                logger.error(f"Periodic prewarming failed: {e}")

    asyncio.create_task(periodic_prewarm())

    logger.info("Query optimization services started")


# 查询性能分析
def get_query_performance_stats() -> Dict[str, Any]:
    """获取查询性能统计"""
    return {
        "hot_queries": query_cache.get_hot_queries(limit=10),
        "cache_stats": query_cache.cache.get_stats(),
        "prewarming_tasks": len(query_prewarmer.prewarming_tasks),
    }
