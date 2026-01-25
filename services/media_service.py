"""
媒体处理服务
从 managers/media_group_manager.py 迁移，负责媒体组处理和去重缓存
"""
import logging
import os
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from telethon import TelegramClient
from utils.core.logger_utils import get_logger
from utils.core.error_handler import handle_errors, handle_telegram_errors
from utils.core.constants import TEMP_DIR, PROCESSED_GROUP_TTL_SECONDS, PROCESSED_GROUP_MAX

logger = get_logger(__name__)

class MediaService:
    """媒体处理服务"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        
    def set_client(self, client: TelegramClient):
        """注入 Telegram 客户端"""
        self.client = client
        
    @handle_telegram_errors(default_return=[])
    async def get_media_group_messages(self, chat_id: int, message_id: int, grouped_id: int) -> List[Any]:
        """获取媒体组消息"""
        if not self.client:
            logger.error("MediaService client not initialized")
            return []
            
        messages = []
        try:
            from utils.network.api_optimization import get_api_optimizer
            api_optimizer = get_api_optimizer()
            
            if api_optimizer:
                # 使用优化的批量获取方法
                messages_data = await api_optimizer.get_messages_batch(
                    chat_id,
                    limit=20,
                    min_id=message_id - 10,
                    max_id=message_id + 10
                )
                
                # 筛选媒体组消息
                for msg in messages_data:
                    if hasattr(msg, 'grouped_id') and msg.grouped_id == grouped_id:
                        messages.append(msg)
            else:
                # 降级到传统方法
                async for message in self.client.iter_messages(
                    chat_id,
                    limit=20,
                    min_id=message_id - 10,
                    max_id=message_id + 10
                ):
                    if message.grouped_id == grouped_id:
                        messages.append(message)
            
            messages.sort(key=lambda x: x.id)
        except Exception as e:
            logger.error(f"获取媒体组消息失败: {str(e)}")
        
        return messages
    
    @handle_errors(default_return=([], None, None))
    async def collect_media_group_info(self, chat_id: int, message_id: int, grouped_id: int) -> Tuple[List[Any], Optional[str], Optional[Any]]:
        """收集媒体组信息"""
        messages = await self.get_media_group_messages(chat_id, message_id, grouped_id)
        caption = None
        buttons = None
        if messages:
            first_message = messages[0]
            caption = first_message.text
            buttons = first_message.buttons if hasattr(first_message, 'buttons') else None
        
        return messages, caption, buttons
    
    @handle_errors(default_return=[])
    async def download_media_group(self, messages: List[Any], temp_dir: str = TEMP_DIR) -> List[str]:
        """下载媒体组"""
        files = []
        for msg in messages:
            if msg.media:
                try:
                    file_path = await msg.download_media(temp_dir)
                    if file_path:
                        files.append(file_path)
                except Exception as e:
                    logger.error(f'下载媒体文件失败: {str(e)}')
        return files
    
    @handle_errors(default_return=None)
    async def cleanup_files(self, file_paths: List[str]) -> None:
        """清理文件"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f'删除临时文件失败 {file_path}: {str(e)}')

    @handle_errors(default_return=([], []))
    async def extract_media_signatures(self, messages: List[Any]) -> Tuple[List[str], List[str]]:
        """提取媒体签名"""
        signatures = []
        file_ids = []
        for message in messages:
            sig, fid = extract_message_signature(message)
            if sig:
                signatures.append(sig)
            if fid:
                file_ids.append(str(fid))
        return signatures, file_ids

    @handle_telegram_errors(default_return=False)
    async def delete_media_group(self, chat_id: int, message_id: int, grouped_id: int) -> bool:
        """删除媒体组的所有消息"""
        messages = await self.get_media_group_messages(chat_id, message_id, grouped_id)
        if not messages:
            return False
            
        try:
            await self.client.delete_messages(chat_id, [m.id for m in messages])
            logger.info(f"成功删除媒体组: {grouped_id}, 包含 {len(messages)} 条消息")
            return True
        except Exception as e:
            logger.error(f"删除媒体组失败: {e}")
            return False

class MemoryProcessedGroupCache:
    """媒体组去重缓存 (内存版)"""
    def __init__(self):
        self._cache: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None

    async def _ensure_cleanup_task(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(60)
            if not self._cache:
                continue
            now = time.time()
            try:
                async with self._lock:
                    expired = [k for k, ts in self._cache.items() if now > ts]
                    for k in expired:
                        self._cache.pop(k, None)
                    if len(self._cache) > PROCESSED_GROUP_MAX:
                        sorted_items = sorted(self._cache.items(), key=lambda x: x[1])
                        to_remove = len(self._cache) - PROCESSED_GROUP_MAX
                        for k, _ in sorted_items[:to_remove]:
                            self._cache.pop(k, None)
            except Exception as e:
                logger.error(f"媒体组缓存清理异常: {e}")

    async def is_processed(self, chat_id: int, group_id: int) -> bool:
        key = f"{chat_id}:{group_id}"
        async with self._lock:
            if key in self._cache:
                if time.time() > self._cache[key]:
                    del self._cache[key]
                    return False
                return True
        return False

    async def mark_processed(self, chat_id: int, group_id: int) -> None:
        key = f"{chat_id}:{group_id}"
        expire_at = time.time() + PROCESSED_GROUP_TTL_SECONDS
        async with self._lock:
            self._cache[key] = expire_at
        await self._ensure_cleanup_task()

def extract_message_signature(message) -> Tuple[Optional[str], Optional[Any]]:
    """提取单条消息的媒体签名"""
    sig = None
    fid = None
    if getattr(message, 'photo', None):
        media_id = getattr(getattr(message, 'photo', None), 'id', None)
        sig = f"photo:{media_id or message.id}"
        fid = media_id
    elif getattr(message, 'document', None) and getattr(message.document, 'id', None):
        sig = f"document:{message.document.id}"
        fid = message.document.id
    elif getattr(message, 'video', None) and getattr(message.video, 'id', None):
        sig = f"video:{message.video.id}"
        fid = message.video.id
    return sig, fid

# 全局单例
media_service = MediaService()
processed_group_cache = MemoryProcessedGroupCache()
