import logging
import asyncio
from typing import Union, Optional, Dict
from datetime import datetime
from sqlalchemy import select
from models.models import Chat
from core.helpers.id_utils import resolve_entity_by_id_variants
from telethon import utils as telethon_utils

logger = logging.getLogger(__name__)

class ChatInfoService:
    """
    聊天信息服务
    负责解析 ChatID 到名称的映射，并提供缓存机制。
    """
    def __init__(self, client=None, db=None):
        self.client = client
        self.db = db
        self._name_cache: Dict[str, str] = {}
        self._last_update: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    def set_client(self, client):
        self.client = client

    def set_db(self, db):
        self.db = db

    async def get_chat_name(self, chat_id: Union[int, str]) -> str:
        """
        获取聊天名称
        优先级：内存缓存 > 数据库 > Telegram API
        """
        str_id = str(chat_id)
        
        # 1. 内存缓存 (TTL 1小时可在此增加判断，暂时简单处理)
        if str_id in self._name_cache:
            return self._name_cache[str_id]
        
        async with self._lock:
            # 双重检查
            if str_id in self._name_cache:
                return self._name_cache[str_id]
            
            # 2. 数据库查询
            name_from_db = await self._get_name_from_db(str_id)
            if name_from_db:
                self._name_cache[str_id] = name_from_db
                return name_from_db
            
            # 3. Telegram API 查询 (需要 client)
            if self.client:
                try:
                    entity, _ = await resolve_entity_by_id_variants(self.client, chat_id)
                    if entity:
                        name = telethon_utils.get_display_name(entity)
                        if name:
                            self._name_cache[str_id] = name
                            # 异步更新到数据库，不阻塞当前返回
                            asyncio.create_task(self._update_chat_in_db(str_id, entity, name))
                            return name
                except Exception as e:
                    logger.warning(f"Failed to resolve chat name for {chat_id} via API: {e}")
            
            # 降级：返回原始 ID
            return str_id

    async def _get_name_from_db(self, chat_id: str) -> Optional[str]:
        if not self.db:
            return None
        
        try:
            from core.helpers.id_utils import build_candidate_telegram_ids
            candidates = list(build_candidate_telegram_ids(chat_id))
            
            async with self.db.session() as session:
                stmt = select(Chat).where(Chat.telegram_chat_id.in_(candidates))
                result = await session.execute(stmt)
                chat = result.scalar_one_or_none()
                if chat and chat.name:
                    return chat.name
        except Exception as e:
            logger.error(f"Error querying chat name from DB for {chat_id}: {e}")
        
        return None

    async def _update_chat_in_db(self, chat_id: str, entity: any, name: str):
        if not self.db:
            return
        
        try:
            from core.helpers.id_utils import normalize_chat_id
            norm_id = normalize_chat_id(chat_id)
            
            async with self.db.session() as session:
                stmt = select(Chat).where(Chat.telegram_chat_id == norm_id)
                result = await session.execute(stmt)
                chat = result.scalar_one_or_none()
                
                if chat:
                    chat.name = name
                    chat.updated_at = datetime.utcnow().isoformat()
                else:
                    # 如果不存在，可能是因为还没有规则用到它，但既然查了就记下来
                    chat = Chat(
                        telegram_chat_id=norm_id,
                        name=name,
                        chat_type=self._get_chat_type(entity)
                    )
                    session.add(chat)
                
                await session.commit()
                logger.debug(f"Updated chat info in DB: {chat_id} -> {name}")
        except Exception as e:
            logger.error(f"Error updating chat info in DB for {chat_id}: {e}")

    def _get_chat_type(self, entity) -> str:
        from telethon.tl.types import Channel, Chat as TGChat, User
        if isinstance(entity, Channel):
            return "channel" if entity.broadcast else "supergroup"
        if isinstance(entity, TGChat):
            return "group"
        if isinstance(entity, User):
            return "private"
        return "unknown"

# 全局单例
chat_info_service = ChatInfoService()
