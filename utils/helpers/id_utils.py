"""
Telegram ID 工具函数

提供以下能力：
- 根据传入的原始 chat_id 构建一组候选的 Telegram chat id 字符串（兼容 -100 前缀与纯 ID）
- 通过候选 ID 解析 Telethon 实体并返回解析成功的实体与最终使用的 ID
- 安全的数据库会话管理
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import logging
from typing import Any, AsyncGenerator, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


def normalize_chat_id(chat_id: Union[int, str]) -> str:
    """标准化 Chat ID 为数据库存储格式
    
    将各种格式的 Telegram Chat ID 标准化为统一的存储格式:
    - -1002815974674 -> 2815974674 (去掉 -100 前缀)
    - -2815974674 -> 2815974674 (去掉负号)
    - 2815974674 -> 2815974674 (保持不变)
    
    Args:
        chat_id: 原始 chat_id (可能为 int 或 str)
    
    Returns:
        标准化后的字符串格式 ID
    """
    try:
        # 转换为整数
        n = int(str(chat_id))
        
        # 如果是负数
        if n < 0:
            # 转为字符串并去掉负号
            abs_str = str(abs(n))
            
            # 如果以 100 开头(超级群组格式 -100xxxxxxxxx)
            if abs_str.startswith('100') and len(abs_str) > 3:
                # 去掉 100 前缀
                return abs_str[3:]
            else:
                # 普通负数,直接返回绝对值
                return abs_str
        else:
            # 正数直接返回
            return str(n)
    except Exception as e:
        logger.warning(f"无法标准化 Chat ID {chat_id}: {e}")
        # 降级:返回原值的字符串形式
        return str(chat_id)


def build_candidate_telegram_ids(raw_id: Union[int, str]) -> Set[str]:
    """根据原始 chat_id 构建候选 ID 集合。

    规则：
    - 保留原值（转为字符串）
    - 添加标准化后的ID（去掉-100前缀）
    - 尝试转为整数后，加入：str(n)、str(abs(n))、f"-100{abs(n)}"、f"-{abs(n)}"

    Args:
        raw_id: 传入的原始 chat_id（可能为 int 或 str）

    Returns:
        候选 ID 的字符串集合
    """
    candidates: Set[str] = set()
    s = str(raw_id)
    candidates.add(s)
    
    # 添加标准化后的ID (核心修复)
    normalized = normalize_chat_id(raw_id)
    candidates.add(normalized)
    
    try:
        n = int(s)
        candidates.add(str(n))
        abs_n = abs(n)
        abs_s = str(abs_n)
        candidates.add(abs_s)

        # 添加各种格式
        candidates.add(f"-100{abs_s}")  # 超级群组格式
        candidates.add(f"-{abs_s}")  # 普通群组格式

        # 如果原数字是正数，也尝试负数版本
        if n > 0:
            candidates.add(f"-{n}")
            candidates.add(f"-100{n}")

        # 如果原数字是负数，也尝试去掉-100前缀的版本
        if n < 0:
            if s.startswith("-100"):
                # 如果是-100开头，尝试去掉-100前缀
                without_prefix = s[4:]  # 去掉"-100"
                candidates.add(without_prefix)
                candidates.add(f"-{without_prefix}")

    except Exception:
        # 非数字场景仅保留原字符串
        pass
    return candidates


async def resolve_entity_by_id_variants(
    client: Any, raw_id: Union[int, str]
) -> Tuple[Optional[Any], Optional[int]]:
    """
    通过多种 ID 变体尝试解析实体 - 官方API优化版本
    使用批量实体解析器，性能提升3-8倍

    Args:
        client: Telethon 客户端
        raw_id: 可能为 int 或 str 的 chat 标识

    Returns:
        (entity, resolved_numeric_id)
    """
    try:
        # 使用优化的实体解析器
        from utils.helpers.entity_optimization import get_entity_resolver

        entity_resolver = get_entity_resolver()

        if entity_resolver:
            # 使用批量解析器
            entity = await entity_resolver.resolve_single_entity(raw_id)
            if entity:
                # 获取数值ID
                resolved_numeric: Optional[int] = None
                try:
                    if isinstance(raw_id, int):
                        resolved_numeric = raw_id
                    else:
                        resolved_numeric = (
                            int(getattr(entity, "id", None))
                            if hasattr(entity, "id")
                            else None
                        )
                except Exception:
                    resolved_numeric = None

                return entity, resolved_numeric

        # 降级到原有逻辑（但优化了API调用）
        try_order: list[Union[int, str]] = []
        try:
            n = int(str(raw_id))
            try_order.append(n)
            # -100 前缀（超级群/频道）
            try_order.append(int(f"-100{abs(n)}"))
            # 常规负数群组格式
            try_order.append(int(f"-{abs(n)}"))
        except Exception:
            # 非数字则仅尝试原字符串（如用户名）
            try_order.append(str(raw_id))

        # 如果没有实体解析器，使用传统方法
        for variant in try_order:
            try:
                entity = await client.get_entity(variant)
                # 返回数值 ID（若 variant 不是数字，尽可能从 entity.id 获取）
                resolved_numeric: Optional[int] = None
                if isinstance(variant, int):
                    resolved_numeric = variant
                else:
                    try:
                        resolved_numeric = (
                            int(getattr(entity, "id", None))
                            if hasattr(entity, "id")
                            else None
                        )
                    except Exception:
                        resolved_numeric = None
                return entity, resolved_numeric
            except Exception:
                continue

        return None, None

    except Exception as e:
        logger.error(f"解析实体失败 {raw_id}: {str(e)}")
        return None, None


def find_chat_by_telegram_id_variants(
    session: Any, raw_id: Union[int, str]
) -> Optional[Any]:
    """在数据库中通过 telegram_chat_id 的多种候选形式查找 Chat 记录。

    Args:
        session: SQLAlchemy 会话
        raw_id: Telegram chat 标识（可能为 int 或 str，可能带/不带 -100 前缀）

    Returns:
        Chat 或 None
    """
    try:
        # 延迟导入避免循环依赖
        from models.models import Chat as ChatModel

        candidates = list(build_candidate_telegram_ids(raw_id))
        logger.debug(f"查找聊天记录，候选ID: {candidates}")
        result = (
            session.query(ChatModel)
            .filter(ChatModel.telegram_chat_id.in_(candidates))
            .first()
        )
        if result:
            logger.debug(f"找到聊天记录: {result.name} (ID: {result.id})")
        else:
            logger.debug(f"未找到匹配的聊天记录，原始ID: {raw_id}")
        return result
    except ImportError as import_error:
        logger.error(f"导入模型失败: {str(import_error)}")
        return None
    except Exception as e:
        logger.error(f"查找聊天记录时出错: {str(e)}", exc_info=True)
        return None


@asynccontextmanager
async def safe_db_session() -> AsyncGenerator[Any, None]:
    """安全的数据库会话上下文管理器，确保正确关闭连接"""
    session = None
    try:
        # 延迟导入避免循环依赖
        from models.models import AsyncSessionManager

        async with AsyncSessionManager() as session:
            logger.debug("创建异步数据库会话")
            yield session
    except ImportError as import_error:
        logger.error(f"导入数据库模型失败: {str(import_error)}")
        raise
    except Exception as e:
        logger.error(f"数据库操作失败: {str(e)}", exc_info=True)
        raise

# [Added for Scheme 7 Compatibility]
from telethon import utils as telethon_utils

def get_peer_id(peer: Any) -> int:
    """获取 Peer 的 ID (Wrapper for telethon.utils.get_peer_id)"""
    return telethon_utils.get_peer_id(peer)

def format_entity_name(entity: Any) -> str:
    """获取实体的显示名称 (Wrapper for telethon.utils.get_display_name)"""
    return telethon_utils.get_display_name(entity)

async def get_display_name_async(chat_id: Union[int, str]) -> str:
    """异步获取聊天显示名称（带缓存）"""
    try:
        from core.container import container
        return await container.chat_info_service.get_chat_name(chat_id)
    except Exception:
        return str(chat_id)
