from typing import List, Optional
import logging
from sqlalchemy import select
from models.models import MediaSignature
from schemas.media import MediaSignatureDTO
from datetime import datetime

logger = logging.getLogger(__name__)

class DedupRepository:
    """去重数据仓库"""
    
    def __init__(self, db):
        self.db = db

    async def find_by_signature(self, chat_id: Optional[str], signature: str) -> Optional[MediaSignatureDTO]:
        """根据签名查找 (chat_id=None 表示全局)"""
        async with self.db.session() as session:
            filters = [MediaSignature.signature == signature]
            if chat_id is not None:
                filters.append(MediaSignature.chat_id == str(chat_id))
            stmt = select(MediaSignature).filter(*filters).limit(1)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
            return MediaSignatureDTO.model_validate(obj) if obj else None

    async def find_by_file_id_or_hash(self, chat_id: Optional[str], file_id: str = None, content_hash: str = None) -> Optional[MediaSignatureDTO]:
        """优先使用 file_id 查找，其次使用 content_hash (chat_id=None 为全局)"""
        async with self.db.session() as session:
            # 基础过滤器
            base_filters = []
            if chat_id is not None:
                base_filters.append(MediaSignature.chat_id == str(chat_id))

            if file_id:
                stmt = select(MediaSignature).filter(
                    *base_filters,
                    MediaSignature.file_id == file_id
                ).limit(1)
                result = await session.execute(stmt)
                rec = result.scalar_one_or_none()
                if rec:
                    return MediaSignatureDTO.model_validate(rec)
            
            if content_hash:
                stmt = select(MediaSignature).filter(
                    *base_filters,
                    MediaSignature.content_hash == content_hash
                ).limit(1)
                result = await session.execute(stmt)
                rec = result.scalar_one_or_none()
                if rec:
                    return MediaSignatureDTO.model_validate(rec)
            
            return None

    async def add_or_update(self, chat_id: str, signature: str, **kwargs) -> bool:
        """新增或更新媒体签名"""
        async with self.db.session() as session:
            try:
                stmt = select(MediaSignature).filter_by(chat_id=str(chat_id), signature=signature)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                now = datetime.utcnow().isoformat()
                
                # [修复核心] 动态获取模型字段，过滤掉非法的 kwargs (如 message_id)
                # 这样即使上层传错了参数，这里也不会报错崩溃
                valid_columns = {c.name for c in MediaSignature.__table__.columns}
                filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_columns}
                
                if existing:
                    # 累加出现次数
                    existing.count = (existing.count or 0) + 1
                    
                    # 更新字段
                    for key, value in filtered_kwargs.items():
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
                        **filtered_kwargs  # 使用过滤后的参数
                    )
                    session.add(new_sig)
                
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"DedupRepository.add_or_update failed: {e}")
                await session.rollback()
                return False

    async def get_duplicates(self, chat_id: str, limit: int = 100) -> List[MediaSignatureDTO]:
        """获取重复媒体记录"""
        async with self.db.session() as session:
            stmt = select(MediaSignature).filter(
                MediaSignature.chat_id == str(chat_id),
                MediaSignature.count > 1
            ).order_by(MediaSignature.count.desc()).limit(limit)
            
            result = await session.execute(stmt)
            objs = result.scalars().all()
            return [MediaSignatureDTO.model_validate(o) for o in objs]

    async def batch_add(self, records: List[dict]) -> bool:
        """批量插入媒体签名记录"""
        if not records:
            return True
            
        async with self.db.session() as session:
            try:
                # 使用 bulk_insert_mappings 提高性能
                await session.run_sync(
                    lambda sync_session: sync_session.bulk_insert_mappings(
                        MediaSignature, records
                    )
                )
                await session.commit()
                logger.debug(f"批量插入 {len(records)} 条媒体签名记录成功")
                return True
            except Exception as e:
                logger.error(f"批量插入媒体签名失败: {e}", exc_info=True)
                await session.rollback()
                return False

    async def delete_by_chat(self, chat_id: str) -> int:
        """删除特定聊天的所有去重记录"""
        async with self.db.session() as session:
            from sqlalchemy import delete
            stmt = delete(MediaSignature).where(MediaSignature.chat_id == str(chat_id))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    # Compatibility Methods for DedupEngine

    async def check_content_hash_duplicate(self, content_hash: str, chat_id: Optional[str], config: dict = None) -> (bool, str):
        """检查内容哈希重复"""
        rec = await self.find_by_file_id_or_hash(chat_id, content_hash=content_hash)
        if rec:
            origin = f"in chat {rec.chat_id}" if chat_id is None else "locally"
            return True, f"内容哈希重复 ({origin}, Last seen: {rec.last_seen})"
        return False, ""

    async def exists_media_signature(self, chat_id: str, signature: str) -> bool:
        """检查签名是否存在"""
        rec = await self.find_by_signature(chat_id, signature)
        return bool(rec)

    async def exists_video_file_id(self, chat_id: str, file_id: str) -> bool:
        """检查视频 FileID 是否存在"""
        rec = await self.find_by_file_id_or_hash(chat_id, file_id=file_id)
        return bool(rec)

    async def add_media_signature(self, chat_id: str, signature: str, message_id: int, content_hash: str = None):
        """添加媒体签名"""
        await self.add_or_update(
            chat_id, 
            signature, 
            # Note: mapping message_id to file_id for storage, verify if this collision is acceptable
            file_id=str(message_id), 
            content_hash=content_hash
        )

    async def add_content_hash(self, chat_id: str, content_hash: str, message_id: int):
        """添加内容哈希记录"""
        # We store content hash as a "signature" of type 'content_hash' or just update the main record?
        # The model has 'content_hash' column.
        # But uniqueness is on (chat_id, signature).
        # We need a signature key.
        # Use content_hash as signature key?
        signature = f"content:{content_hash}"
        await self.add_or_update(chat_id, signature, content_hash=content_hash)

    async def add_text_fingerprint(self, chat_id: str, fingerprint: int, message_id: int):
        """添加文本指纹"""
        signature = f"text_fp:{fingerprint}"
        await self.add_or_update(chat_id, signature)

    async def delete_media_signature(self, chat_id: str, signature: str):
        """删除签名"""
        async with self.db.session() as session:
            from sqlalchemy import delete
            stmt = delete(MediaSignature).filter_by(chat_id=str(chat_id), signature=signature)
            await session.execute(stmt)
            await session.commit()

    async def delete_content_hash(self, chat_id: str, content_hash: str):
        """删除内容哈希"""
        # Since we mapped it to "content:{hash}"
        signature = f"content:{content_hash}"
        await self.delete_media_signature(chat_id, signature)

    async def save_config(self, config: dict):
        """保存全局去重配置到 SystemConfiguration"""
        try:
            import json
            from models.system import SystemConfiguration
            
            async with self.db.session() as session:
                key = "dedup_global_config"
                value = json.dumps(config)
                
                # Check existing
                stmt = select(SystemConfiguration).filter_by(key=key)
                result = await session.execute(stmt)
                obj = result.scalar_one_or_none()
                
                if obj:
                    obj.value = value
                    obj.updated_at = datetime.utcnow().isoformat()
                else:
                    obj = SystemConfiguration(
                        key=key,
                        value=value,
                        data_type="json",
                        description="Global Deduplication Configuration"
                    )
                    session.add(obj)
                await session.commit()
                logger.debug("去重全局配置已保存")
        except Exception as e:
            logger.error(f"Save dedup config failed: {e}")

    async def load_config(self) -> dict:
        """从 SystemConfiguration 加载配置"""
        try:
            import json
            from models.system import SystemConfiguration
            
            async with self.db.session() as session:
                stmt = select(SystemConfiguration).filter_by(key="dedup_global_config")
                result = await session.execute(stmt)
                obj = result.scalar_one_or_none()
                
                if obj and obj.value:
                    return json.loads(obj.value)
        except Exception as e:
            logger.error(f"Load dedup config failed: {e}")
        return {}
