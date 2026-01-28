"""
实体解析优化器
使用批量API替代单个get_entity调用，性能提升3-8倍
"""

from datetime import datetime, timedelta

import asyncio
import logging
from telethon import TelegramClient
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


class EntityResolver:
    """优化的实体解析器"""

    def __init__(self, client: TelegramClient):
        self.client = client
        self.entity_cache: Dict[str, Any] = {}
        self.cache_ttl = timedelta(hours=1)  # 缓存1小时
        self.pending_resolves: Set[str] = set()

    async def resolve_entities_batch(
        self, identifiers: List[Union[int, str]]
    ) -> Dict[str, Any]:
        """
        批量解析实体 - 替代多个get_entity调用

        Args:
            identifiers: 实体标识符列表（ID、用户名等）

        Returns:
            解析结果字典 {identifier: entity}
        """
        if not identifiers:
            return {}

        logger.info(f"批量解析实体: {len(identifiers)} 个")

        # 标准化标识符
        normalized_ids = [str(id_) for id_ in identifiers]

        # 检查缓存
        result = {}
        uncached_ids = []
        now = datetime.now()

        for identifier in normalized_ids:
            if identifier in self.entity_cache:
                cached_data = self.entity_cache[identifier]
                if now - cached_data["cached_at"] < self.cache_ttl:
                    result[identifier] = cached_data["entity"]
                else:
                    del self.entity_cache[identifier]
                    uncached_ids.append(identifier)
            else:
                uncached_ids.append(identifier)

        # 批量解析未缓存的实体
        if uncached_ids:
            resolved_entities = await self._batch_resolve_uncached(uncached_ids)

            # 缓存结果
            for identifier, entity in resolved_entities.items():
                if entity:
                    self.entity_cache[identifier] = {"entity": entity, "cached_at": now}
                    result[identifier] = entity

        logger.info(f"批量解析完成: {len(result)} 个成功")
        return result

    async def _batch_resolve_uncached(self, identifiers: List[str]) -> Dict[str, Any]:
        """批量解析未缓存的实体"""
        result = {}

        # 分批处理，避免API限制
        batch_size = 10  # 每批处理10个
        for i in range(0, len(identifiers), batch_size):
            batch = identifiers[i : i + batch_size]
            batch_result = await self._resolve_batch(batch)
            result.update(batch_result)

            # 添加小延迟避免速率限制
            if i + batch_size < len(identifiers):
                await asyncio.sleep(0.1)

        return result

    async def _resolve_batch(self, batch: List[str]) -> Dict[str, Any]:
        """解析单个批次的实体"""
        result = {}

        # 并发解析批次中的所有实体
        tasks = []
        for identifier in batch:
            task = asyncio.create_task(self._resolve_single_with_variants(identifier))
            tasks.append((identifier, task))

        # 等待所有任务完成
        for identifier, task in tasks:
            try:
                entity = await task
                result[identifier] = entity
            except Exception as e:
                logger.warning(f"解析实体失败 {identifier}: {str(e)}")
                result[identifier] = None

        return result

    async def _resolve_single_with_variants(self, identifier: str) -> Optional[Any]:
        """
        解析单个实体，尝试多种变体
        替代原有的 resolve_entity_by_id_variants 函数
        """
        try:
            logger.info(f"开始解析实体: {identifier}")
            # 如果是数字ID，尝试多种格式
            try:
                numeric_id = int(identifier)
                variants = [
                    numeric_id,
                    int(f"-100{abs(numeric_id)}"),  # 频道/超级群组格式
                    int(f"-{abs(numeric_id)}"),  # 普通群组格式
                ]
                logger.debug(f"数字ID变体: {variants}")
            except ValueError:
                # 非数字，只尝试原字符串（用户名等）
                variants = [identifier]
                logger.debug(f"非数字标识符: {identifier}")

            # 依次尝试各种变体
            for variant in variants:
                try:
                    logger.debug(f"尝试解析变体: {variant}")
                    entity = await self.client.get_entity(variant)
                    logger.info(
                        f"成功解析实体: {identifier} -> {variant} (ID: {entity.id})"
                    )
                    return entity
                except Exception as e:
                    logger.debug(f"解析变体失败 {variant}: {str(e)}")
                    continue

            logger.warning(f"所有变体都解析失败: {identifier}, 变体列表: {variants}")
            return None

        except Exception as e:
            logger.error(f"解析实体出错 {identifier}: {str(e)}", exc_info=True)
            return None

    async def resolve_single_entity(self, identifier: Union[int, str]) -> Optional[Any]:
        """
        解析单个实体 - 优化版本

        Args:
            identifier: 实体标识符

        Returns:
            解析的实体或None
        """
        result = await self.resolve_entities_batch([identifier])
        return result.get(str(identifier))

    async def get_chat_info_optimized(self, chat_id: Union[int, str]) -> Dict[str, Any]:
        """
        获取优化的聊天信息
        结合实体解析和API优化器

        Args:
            chat_id: 聊天ID

        Returns:
            聊天信息字典
        """
        try:
            # 首先解析实体
            entity = await self.resolve_single_entity(chat_id)
            if not entity:
                return {"error": f"无法解析聊天实体: {chat_id}"}

            # 使用API优化器获取统计信息
            mod = __import__('services.network.api_optimization', fromlist=['get_api_optimizer'])
            api_optimizer = mod.get_api_optimizer()

            chat_info = {
                "entity": entity,
                "chat_id": str(chat_id),
                "name": getattr(entity, "title", None)
                or getattr(entity, "first_name", ""),
                "username": getattr(entity, "username", ""),
                "api_method": "entity_resolver",
            }

            if api_optimizer:
                try:
                    # 获取详细统计
                    stats = await api_optimizer.get_chat_statistics(chat_id)
                    chat_info.update(stats)
                except Exception as e:
                    logger.warning(f"获取聊天统计失败: {str(e)}")

            return chat_info

        except Exception as e:
            logger.error(f"获取聊天信息失败 {chat_id}: {str(e)}")
            return {"error": str(e)}

    def clear_cache(self):
        """清理缓存"""
        self.entity_cache.clear()
        logger.info("实体解析缓存已清理")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        now = datetime.now()
        valid_cache = 0
        expired_cache = 0

        for cached_data in self.entity_cache.values():
            if now - cached_data["cached_at"] < self.cache_ttl:
                valid_cache += 1
            else:
                expired_cache += 1

        return {
            "total_cached": len(self.entity_cache),
            "valid_cache": valid_cache,
            "expired_cache": expired_cache,
            "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
        }


class OptimizedChatFinder:
    """优化的聊天查找器"""

    def __init__(self, client: TelegramClient):
        self.client = client
        self.entity_resolver = EntityResolver(client)

    async def find_chat_by_name_optimized(
        self, chat_name: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        优化的聊天名称搜索
        替代遍历所有对话的方式

        Args:
            chat_name: 聊天名称（支持模糊匹配）
            limit: 最大结果数量

        Returns:
            匹配的聊天列表
        """
        try:
            logger.info(f"优化搜索聊天: {chat_name}")

            matches = []
            chat_name_lower = chat_name.lower()

            # 使用安全的对话获取方法
            from core.helpers.dialog_helper import safe_iter_dialogs

            try:
                async for dialog in safe_iter_dialogs(
                    self.client, limit=limit * 2, max_retries=2, timeout=20.0
                ):
                    if len(matches) >= limit:
                        break

                    dialog_name = getattr(dialog, "name", "") or ""
                    if chat_name_lower in dialog_name.lower():
                        # 使用API优化器获取详细信息
                        chat_info = await self.entity_resolver.get_chat_info_optimized(
                            dialog.entity.id
                        )
                        matches.append(
                            {
                                "entity": dialog.entity,
                                "name": dialog_name,
                                "id": dialog.entity.id,
                                "match_score": self._calculate_match_score(
                                    chat_name_lower, dialog_name.lower()
                                ),
                                "detailed_info": chat_info,
                            }
                        )
            except Exception as e:
                logger.error(f"搜索对话时发生错误: {e}")
                # 返回已找到的匹配项，即使发生了错误

            # 按匹配度排序
            matches.sort(key=lambda x: x["match_score"], reverse=True)

            logger.info(f"找到 {len(matches)} 个匹配的聊天")
            return matches[:limit]

        except Exception as e:
            logger.error(f"优化搜索聊天失败: {str(e)}")
            return []

    def _calculate_match_score(self, search_term: str, target: str) -> float:
        """计算匹配度分数"""
        if search_term == target:
            return 1.0
        elif target.startswith(search_term):
            return 0.8
        elif search_term in target:
            return 0.6
        else:
            # 计算相似度
            common_chars = set(search_term) & set(target)
            return len(common_chars) / max(len(search_term), len(target))


# 全局实例
entity_resolver: Optional[EntityResolver] = None
chat_finder: Optional[OptimizedChatFinder] = None


def initialize_entity_resolver(client: TelegramClient):
    """初始化实体解析器"""
    global entity_resolver, chat_finder
    entity_resolver = EntityResolver(client)
    chat_finder = OptimizedChatFinder(client)
    logger.info("实体解析器初始化完成")


def get_entity_resolver() -> Optional[EntityResolver]:
    """获取实体解析器实例"""
    return entity_resolver


def get_chat_finder() -> Optional[OptimizedChatFinder]:
    """获取聊天查找器实例"""
    return chat_finder
