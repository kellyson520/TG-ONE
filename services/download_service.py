import os
import asyncio
import logging
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
from core.helpers.media.media import download_media_with_retry
from core.config import settings

logger = logging.getLogger(__name__)

class DownloadService:
    def __init__(self, client, download_path=None, max_concurrent=2):
        self.client = client
        # 使用 settings 中的 DOWNLOAD_DIR 或默认值
        self.base_path = download_path or str(settings.DOWNLOAD_DIR)
        # 限制并发数为 2，防止 1G 内存被大文件撑爆
        self.semaphore = asyncio.Semaphore(max_concurrent) 
        os.makedirs(self.base_path, exist_ok=True)

    # [Scheme 7 Fix] 重命名以匹配 WorkerService 的调用
    async def push_to_queue(self, message, sub_folder: str = "default"):
        """
        执行下载任务 (实际上是直接执行，由 Semaphore 控制并发，而非内部 Queue)
        Args:
            message: Telethon Message 对象
            sub_folder: 子文件夹名称 (通常是 chat_id)
        """
        async with self.semaphore:
            try:
                # 1. 健壮的文件名获取逻辑
                file_name = None
                
                # 尝试从 Document 属性获取
                if hasattr(message, 'file') and message.file and hasattr(message.file, 'name') and message.file.name:
                    file_name = message.file.name
                
                # 尝试从 Attributes 获取
                if not file_name and hasattr(message, 'media') and hasattr(message.media, 'document'):
                    for attr in getattr(message.media.document, 'attributes', []):
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            break
                
                # 兜底：使用 message_id + 扩展名
                if not file_name:
                    from telethon.utils import get_extension
                    ext = get_extension(message.media) or '.bin'
                    file_name = f"{message.id}{ext}"

                # 2. 构建路径
                save_dir = os.path.join(self.base_path, str(sub_folder))
                os.makedirs(save_dir, exist_ok=True)
                
                # 防止路径遍历攻击 (简单的)
                file_name = os.path.basename(file_name)
                file_path = os.path.join(save_dir, file_name)

                if os.path.exists(file_path):
                    logger.info(f"💾 文件已存在，跳过: {file_path}")
                    return file_path

                logger.info(f"⬇️ 开始下载: {file_name} -> {sub_folder}")
                
                # 3. 执行下载
                path = await self.client.download_media(message, file=file_path)
                
                logger.info(f"✅ 下载完成: {path}")
                return path

            except Exception as e:
                logger.error(f"❌ 下载失败 MsgID={message.id}: {e}")
                raise e # 抛出异常让 Worker 记录为 failed
    
    async def shutdown(self):
        """关闭下载器，等待当前分片下载完成（或取消）"""
        logger.info("关闭下载器，等待当前下载完成...")
        # 这里可以添加逻辑来取消或等待当前下载完成
        # 目前的实现只是记录日志，因为信号量会自动管理并发下载
        logger.info("下载器已关闭")