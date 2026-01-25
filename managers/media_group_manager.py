"""
统一的媒体组处理管理器
集成官方API优化，减少重复代码，提升性能
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

class MediaGroupManager:
    """统一的媒体组处理管理器"""
    
    def __init__(self, client: TelegramClient):
        self.client = client
        
    @handle_telegram_errors(default_return=[])
    async def get_media_group_messages(self, chat_id: int, message_id: int, grouped_id: int) -> List[Any]:
        """
        获取媒体组消息 - 优先使用官方API优化
        
        Args:
            chat_id: 聊天ID
            message_id: 消息ID
            grouped_id: 媒体组ID
            
        Returns:
            List[Any]: 媒体组消息列表
        """
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
                        
                logger.info(f"API优化器获取到 {len(messages)} 条媒体组消息")
            else:
                # 降级到传统方法
                logger.warning("API优化器未初始化，使用传统方法获取媒体组消息")
                async for message in self.client.iter_messages(
                    chat_id,
                    limit=20,
                    min_id=message_id - 10,
                    max_id=message_id + 10
                ):
                    if message.grouped_id == grouped_id:
                        messages.append(message)
            
            # 按消息ID排序确保顺序正确
            messages.sort(key=lambda x: x.id)
            
        except Exception as e:
            logger.error(f"获取媒体组消息失败: {str(e)}")
        
        return messages
    
    @handle_errors(default_return=([], None, None))
    async def collect_media_group_info(self, chat_id: int, message_id: int, grouped_id: int) -> Tuple[List[Any], Optional[str], Optional[Any]]:
        """
        收集媒体组信息，包括消息、标题和按钮
        
        Args:
            chat_id: 聊天ID
            message_id: 消息ID
            grouped_id: 媒体组ID
            
        Returns:
            Tuple[List[Any], Optional[str], Optional[Any]]: (消息列表, 标题, 按钮)
        """
        messages = await self.get_media_group_messages(chat_id, message_id, grouped_id)
        
        caption = None
        buttons = None
        
        # 从第一条消息获取标题和按钮
        if messages:
            first_message = messages[0]
            caption = first_message.text
            buttons = first_message.buttons if hasattr(first_message, 'buttons') else None
        
        return messages, caption, buttons
    
    @handle_errors(default_return=[])
    async def download_media_group(self, messages: List[Any], temp_dir: str = TEMP_DIR) -> List[str]:
        """
        下载媒体组中的所有媒体文件
        
        Args:
            messages: 媒体组消息列表
            temp_dir: 临时目录
            
        Returns:
            List[str]: 下载的文件路径列表
        """
        files = []
        
        for msg in messages:
            if msg.media:
                try:
                    file_path = await msg.download_media(temp_dir)
                    if file_path:
                        files.append(file_path)
                        logger.debug(f'已下载媒体文件: {file_path}')
                except Exception as e:
                    logger.error(f'下载媒体文件失败: {str(e)}')
        
        logger.info(f"媒体组下载完成，共 {len(files)} 个文件")
        return files
    
    @handle_errors(default_return=None)
    async def cleanup_files(self, file_paths: List[str]) -> None:
        """
        清理临时文件
        
        Args:
            file_paths: 文件路径列表
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f'已删除临时文件: {file_path}')
            except Exception as e:
                logger.error(f'删除临时文件失败 {file_path}: {str(e)}')
    
    @handle_errors(default_return=([], []))
    async def extract_media_signatures(self, messages: List[Any]) -> Tuple[List[str], List[str]]:
        """
        提取媒体组签名和文件ID用于去重
        
        Args:
            messages: 媒体组消息列表
            
        Returns:
            Tuple[List[str], List[str]]: (签名列表, 文件ID列表)
        """
        signatures = []
        file_ids = []
        
        for message in messages:
            sig, fid = self._extract_single_signature(message)
            if sig:
                signatures.append(sig)
            if fid:
                file_ids.append(str(fid))
        
        return signatures, file_ids
    
    def _extract_single_signature(self, message) -> Tuple[Optional[str], Optional[Any]]:
        """
        从单条消息提取媒体签名和文件ID
        
        Args:
            message: 消息对象
            
        Returns:
            Tuple[Optional[str], Optional[Any]]: (签名, 文件ID)
        """
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
    
    @handle_telegram_errors(default_return=None)
    async def delete_media_group(self, chat_id: int, message_id: int, grouped_id: int) -> bool:
        """
        删除媒体组中的所有消息
        
        Args:
            chat_id: 聊天ID
            message_id: 消息ID
            grouped_id: 媒体组ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            messages = await self.get_media_group_messages(chat_id, message_id, grouped_id)
            
            for msg in messages:
                try:
                    await msg.delete()
                    logger.debug(f'已删除媒体组消息 ID: {msg.id}')
                except Exception as e:
                    logger.error(f'删除消息失败 {msg.id}: {str(e)}')
            
            logger.info(f"媒体组删除完成，共删除 {len(messages)} 条消息")
            return True
            
        except Exception as e:
            logger.error(f"删除媒体组失败: {str(e)}")
        return False


# 全局管理器实例
_media_group_manager: Optional[MediaGroupManager] = None

def get_media_group_manager() -> Optional[MediaGroupManager]:
    """获取媒体组管理器实例"""
    return _media_group_manager

def initialize_media_group_manager(client: TelegramClient):
    """初始化媒体组管理器"""
    global _media_group_manager
    _media_group_manager = MediaGroupManager(client)
    logger.info("媒体组管理器初始化完成")

async def cleanup_media_group_manager():
    """清理媒体组管理器"""
    global _media_group_manager
    _media_group_manager = None
    logger.info("媒体组管理器已清理")

class ProcessedGroupCache:
    """
    媒体组去重缓存 (内存优化版)
    使用单一清理任务替代每个组的独立任务
    """
    def __init__(self):
        # key -> expire_time
        self._cache: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None

    async def _ensure_cleanup_task(self):
        """确保清理任务在运行"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self):
        """定期清理过期键"""
        while True:
            await asyncio.sleep(60)  # 每分钟清理一次
            if not self._cache:
                continue
            
            now = time.time()
            try:
                async with self._lock:
                    # 找出所有过期的键
                    expired = [k for k, ts in self._cache.items() if now > ts]
                    for k in expired:
                        self._cache.pop(k, None)
                    
                    # 如果缓存过大，强制清理最旧的
                    if len(self._cache) > PROCESSED_GROUP_MAX:
                        # 按过期时间排序，删除最早过期的
                        sorted_items = sorted(self._cache.items(), key=lambda x: x[1])
                        to_remove = len(self._cache) - PROCESSED_GROUP_MAX
                        for k, _ in sorted_items[:to_remove]:
                            self._cache.pop(k, None)
                            
                    logger.debug(f"媒体组缓存清理: 移除 {len(expired)} 个过期项，剩余 {len(self._cache)}")
            except Exception as e:
                logger.error(f"媒体组缓存清理异常: {e}")

    async def is_processed(self, chat_id: int, group_id: int) -> bool:
        key = f"{chat_id}:{group_id}"
        async with self._lock:
            if key in self._cache:
                # 检查是否过期（懒加载清理）
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
        
        # 确保后台清理任务在运行
        await self._ensure_cleanup_task()
        logger.debug(f"标记媒体组为已处理: {key}")

_processed_group_cache: Optional[ProcessedGroupCache] = None

def get_processed_group_cache() -> ProcessedGroupCache:
    global _processed_group_cache
    if _processed_group_cache is None:
        _processed_group_cache = ProcessedGroupCache()
    return _processed_group_cache

def extract_message_signature(message) -> Tuple[Optional[str], Optional[Any]]:
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
