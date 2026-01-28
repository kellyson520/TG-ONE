"""
Telegram ID 工具函数

提供以下能力：
- 根据传入的原始 chat_id 构建一组候选的 Telegram chat id 字符串（兼容 -100 前缀与纯 ID）
- 通过候选 ID 解析 Telethon 实体并返回解析成功的实体与最终使用的 ID
- 安全的数据库会话管理
"""

from __future__ import annotations


import logging
from typing import Any, Optional, Set, Tuple, Union

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
        from core.helpers.entity_optimization import get_entity_resolver

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


def find_chat_by_telegram_id_variants(session: Any, raw_id: Union[int, str]) -> Optional[Any]:
    """
    根据原始 ID 尝试在数据库中查找聊天(支持多种 ID 变体)
    
    Args:
        session: 数据库会话
        raw_id: 原始 ID (int, str)
        
    Returns:
        Chat 模型实例 或 None
    """
    try:
        # 延迟导入以避免循环依赖
        from models.models import Chat
        from sqlalchemy import select
        
        candidates = build_candidate_telegram_ids(raw_id)
        if not candidates:
            return None
            
        # 查询 telegram_chat_id 在 candidates 中的记录
        stmt = select(Chat).where(Chat.telegram_chat_id.in_(candidates))
        result = session.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        logger.error(f"在数据库中查找聊天变体失败 {raw_id}: {e}")
        return None


async def get_or_create_chat_async(client: Any, chat_input: str) -> Tuple[str, str, Any]:
    """
    解析聊天输入并确保在数据库中存在
    
    Args:
        client: Telethon 客户端
        chat_input: 聊天 ID、用户名或链接
        
    Returns:
        (display_name, telegram_chat_id, chat_model_instance)
    """
    from core.container import container
    from models.models import Chat
    from sqlalchemy import select
    import telethon.utils as telethon_utils

    # 1. 尝试解析实体
    entity, numeric_id = await resolve_entity_by_id_variants(client, chat_input)
    if not entity:
        return str(chat_input), str(chat_input), None

    display_name = telethon_utils.get_display_name(entity)
    telegram_chat_id = str(numeric_id) if numeric_id is not None else str(chat_input)

    # 2. 数据库查重或创建
    async with container.db.session() as session:
        # 使用标准化 ID 查找
        norm_id = normalize_chat_id(telegram_chat_id)
        candidates = build_candidate_telegram_ids(telegram_chat_id)
        
        stmt = select(Chat).where(Chat.telegram_chat_id.in_(candidates))
        result = await session.execute(stmt)
        chat = result.scalars().first()
        
        if not chat:
            # 获取聊天类型
            from telethon.tl.types import Channel, Chat as TGChat, User
            chat_type = "unknown"
            if isinstance(entity, Channel):
                chat_type = "channel" if entity.broadcast else "supergroup"
            elif isinstance(entity, TGChat):
                chat_type = "group"
            elif isinstance(entity, User):
                chat_type = "private"
                
            chat = Chat(
                telegram_chat_id=norm_id,
                name=display_name,
                type=chat_type,
                title=display_name
            )
            session.add(chat)
            await session.commit()
            await session.refresh(chat)
        else:
            # 更新名称
            if chat.name != display_name:
                chat.name = display_name
                await session.commit()
                await session.refresh(chat)
        
        return display_name, telegram_chat_id, chat


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
