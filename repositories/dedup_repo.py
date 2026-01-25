import logging
from typing import List, Optional, Tuple
from sqlalchemy import select
from models.models import MediaSignature
from datetime import datetime

logger = logging.getLogger(__name__)

class DedupRepository:
    """去重数据仓库"""
    
    def __init__(self, db):
        self.db = db

    async def find_by_signature(self, chat_id: str, signature: str) -> Optional[MediaSignature]:
        """根据签名查找"""
        async with self.db.session() as session:
            stmt = select(MediaSignature).filter_by(chat_id=str(chat_id), signature=signature)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def find_by_file_id_or_hash(self, chat_id: str, file_id: str = None, content_hash: str = None) -> Optional[MediaSignature]:
        """优先使用 file_id 查找，其次使用 content_hash"""
        async with self.db.session() as session:
            if file_id:
                stmt = select(MediaSignature).filter(
                    MediaSignature.chat_id == str(chat_id),
                    MediaSignature.file_id == file_id
                ).limit(1)
                result = await session.execute(stmt)
                rec = result.scalar_one_or_none()
                if rec:
                    return rec
            
            if content_hash:
                stmt = select(MediaSignature).filter(
                    MediaSignature.chat_id == str(chat_id),
                    MediaSignature.content_hash == content_hash
                ).limit(1)
                result = await session.execute(stmt)
                rec = result.scalar_one_or_none()
                if rec:
                    return rec
            
            return None

    async def add_or_update(self, chat_id: str, signature: str, **kwargs) -> bool:
        """新增或更新媒体签名"""
        async with self.db.session() as session:
            try:
                stmt = select(MediaSignature).filter_by(chat_id=str(chat_id), signature=signature)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                now = datetime.utcnow().isoformat()
                
                if existing:
                    # 累加出现次数
                    existing.count = (existing.count or 0) + 1
                    
                    # 更新字段
                    for key, value in kwargs.items():
                        if value and not getattr(existing, key, None):
                            setattr(existing, key, value)
                    
                    existing.updated_at = now
                    existing.last_seen = now
                else:
                    # 创建新记录
                    new_sig = MediaSignature(
                        chat_id=str(chat_id),
                        signature=signature,
                        count=1,
                        created_at=now,
                        updated_at=now,
                        last_seen=now,
                        **kwargs
                    )
                    session.add(new_sig)
                
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"DedupRepository.add_or_update failed: {e}")
                await session.rollback()
                return False

    async def get_duplicates(self, chat_id: str, limit: int = 100) -> List[MediaSignature]:
        """获取重复媒体记录"""
        async with self.db.session() as session:
            stmt = select(MediaSignature).filter(
                MediaSignature.chat_id == str(chat_id),
                MediaSignature.count > 1
            ).order_by(MediaSignature.count.desc()).limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()

    async def delete_by_chat(self, chat_id: str) -> int:
        """删除特定聊天的所有去重记录"""
        async with self.db.session() as session:
            from sqlalchemy import delete
            stmt = delete(MediaSignature).where(MediaSignature.chat_id == str(chat_id))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
