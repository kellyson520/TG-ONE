from sqlalchemy import select
from models.models import ForwardRule, MediaExtensions, PushConfig, RuleSync, RSSConfig
from core.logging import get_logger

logger = get_logger(__name__)

class DBOperations:
    """数据库操作封装类 (兼容层)"""
    
    @classmethod
    async def create(cls):
        return cls()
        
    async def get_media_extensions(self, session, rule_id):
        """获取规则的媒体扩展名配置"""
        stmt = select(MediaExtensions).filter_by(rule_id=rule_id)
        result = await session.execute(stmt)
        return result.scalars().all()
        
    async def get_push_configs(self, session, rule_id):
        """获取规则的推送配置"""
        stmt = select(PushConfig).filter_by(rule_id=rule_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_rule_syncs(self, session, rule_id):
        """获取规则的同步配置"""
        stmt = select(RuleSync).filter_by(rule_id=rule_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_rss_config(self, session, rule_id):
        """获取规则的RSS配置"""
        stmt = select(RSSConfig).filter_by(rule_id=rule_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_media_record_by_fileid_or_hash(self, session, chat_id: str, file_id: str = None, content_hash: str = None):
        """返回命中的 MediaSignature 记录（优先 file_id，其次 content_hash），用于严格复核。"""
        from models.models import MediaSignature
        try:
            if file_id:
                stmt = select(MediaSignature).filter(
                    MediaSignature.chat_id == str(chat_id),
                    MediaSignature.file_id == file_id
                ).limit(1)
                result = await session.execute(stmt)
                rec = result.scalar_one_or_none()
                if rec:
                    logger.debug(f"通过file_id找到媒体记录: {file_id} (聊天ID: {chat_id})")
                    return rec
            if content_hash:
                stmt = select(MediaSignature).filter(
                    MediaSignature.chat_id == str(chat_id),
                    MediaSignature.content_hash == content_hash
                ).limit(1)
                result = await session.execute(stmt)
                rec = result.scalar_one_or_none()
                if rec:
                    logger.debug(f"通过content_hash找到媒体记录: {content_hash} (聊天ID: {chat_id})")
                    return rec
            logger.debug(f"未找到匹配的媒体记录 (聊天ID: {chat_id}, file_id: {file_id}, content_hash: {content_hash})")
            return None
        except Exception as e:
            logger.error(f"数据库错误导致查找媒体记录失败 (聊天ID: {chat_id}, file_id: {file_id}, content_hash: {content_hash}). 错误: {str(e)}")
            return None

    async def add_media_signature(self, session, chat_id: str, signature: str, message_id: int = None,
                                  media_type: str = None, file_size: int = None, file_name: str = None,
                                  mime_type: str = None, duration: int = None, width: int = None, height: int = None,
                                  file_id: str = None, content_hash: str = None) -> bool:
        """新增媒体签名记录（若不存在），并保存更丰富的特征（包含 file_id 与 content_hash）"""
        from models.models import MediaSignature
        from datetime import datetime
        try:
            stmt = select(MediaSignature).filter_by(chat_id=str(chat_id), signature=signature)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                try:
                    # 累加出现次数
                    current = getattr(existing, 'count', 1) or 1
                    existing.count = current + 1
                    # 如未记录过message_id且本次提供，则补充
                    if message_id and not existing.message_id:
                        existing.message_id = message_id
                    # 更新附加信息（尽量不覆盖已有有效值）
                    if media_type and not existing.media_type:
                        existing.media_type = media_type
                    if file_size and not existing.file_size:
                        existing.file_size = file_size
                    if file_name and not existing.file_name:
                        existing.file_name = file_name
                    if mime_type and not existing.mime_type:
                        existing.mime_type = mime_type
                    if duration and not existing.duration:
                        existing.duration = duration
                    if width and not existing.width:
                        existing.width = width
                    if height and not existing.height:
                        existing.height = height
                    if file_id and not existing.file_id:
                        existing.file_id = file_id
                    if content_hash and not existing.content_hash:
                        existing.content_hash = content_hash
                    
                    existing.updated_at = datetime.utcnow().isoformat()
                    existing.last_seen = datetime.utcnow().isoformat()
                    return True
                except Exception as ue:
                    logger.warning(f"更新现有签名失败: {ue}")
                    return False
            
            # 创建新记录
            new_sig = MediaSignature(
                chat_id=str(chat_id),
                signature=signature,
                message_id=message_id,
                media_type=media_type,
                file_size=file_size,
                file_name=file_name,
                mime_type=mime_type,
                duration=duration,
                width=width,
                height=height,
                file_id=file_id,
                content_hash=content_hash,
                count=1,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                last_seen=datetime.utcnow().isoformat()
            )
            session.add(new_sig)
            return True
        except Exception as e:
            logger.error(f"添加媒体签名失败: {str(e)}")
            return False

    async def scan_duplicate_media(self, session, chat_id: str):
        """扫描指定聊天中的重复媒体签名
        
        Args:
            session: 数据库会话
            chat_id: 聊天ID
            
        Returns:
            tuple: (dup_list, dup_map)
                - dup_list: 重复签名列表 (count > 1)
                - dup_map: 签名 -> 出现次数映射
        """
        from models.models import MediaSignature
        try:
            # 查询该聊天中所有 count > 1 的媒体签名
            stmt = select(MediaSignature).filter(
                MediaSignature.chat_id == str(chat_id),
                MediaSignature.count > 1
            ).order_by(MediaSignature.count.desc())
            
            result = await session.execute(stmt)
            duplicates = result.scalars().all()
            
            # 构建返回数据
            dup_list = []
            dup_map = {}
            
            for dup in duplicates:
                dup_list.append(dup.signature)
                dup_map[dup.signature] = dup.count
            
            logger.info(f"扫描聊天 {chat_id} 发现 {len(dup_list)} 个重复媒体签名")
            return dup_list, dup_map
            
        except Exception as e:
            logger.error(f"扫描重复媒体失败: {str(e)}")
            return [], {}

    async def get_duplicate_media_records(self, session, chat_id: str, limit: int = 10):
        """获取重复媒体的完整记录
        
        Args:
            session: 数据库会话
            chat_id: 聊天ID
            limit: 返回数量限制
            
        Returns:
            list[MediaSignature]: 重复媒体记录列表
        """
        from models.models import MediaSignature
        try:
            stmt = select(MediaSignature).filter(
                MediaSignature.chat_id == str(chat_id),
                MediaSignature.count > 1
            ).order_by(MediaSignature.count.desc()).limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取重复媒体记录失败: {str(e)}")
            return []
