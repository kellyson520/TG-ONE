"""
智能去重服务层
纯业务逻辑，不包含UI相关代码
"""
from typing import Dict, List, Tuple, Any
import logging
from models.models import MediaSignature
# [Refactor Fix] 更新 smart_dedup 路径
from services.dedup.engine import smart_deduplicator
from services.bloom_filter import bloom_filter_service

logger = logging.getLogger(__name__)

class DeduplicationService:
    """智能去重业务逻辑服务"""
    
    def __init__(self, db=None):
        """初始化去重服务"""
        self.db = db
        self.coordinator = None
        self._repo = None

    @property
    def repo(self):
        if self._repo is None:
            from core.container import container
            self._repo = container.dedup_repo
        return self._repo

    @property
    def stats_repo(self):
        if not hasattr(self, '_stats_repo') or self._stats_repo is None:
            from core.container import container
            self._stats_repo = container.stats_repo
        return self._stats_repo

    def set_coordinator(self, coordinator):
        """注入 GroupCommitCoordinator"""
        self.coordinator = coordinator
    
    async def get_dedup_config(self) -> Dict[str, Any]:
        """获取去重配置"""
        try:
            # 确保加载配置
            await smart_deduplicator.load_config()

            # [Refactor Fix] 直接使用顶层导入的实例
            config = smart_deduplicator.config
            stats = smart_deduplicator.get_stats()
            
            return {
                'config': config,
                'stats': stats,
                'enabled_features': self._get_enabled_features(config)
            }
            
        except Exception as e:
            logger.error(f"获取去重配置失败: {e}", exc_info=True)
            return {
                'config': {},
                'stats': {'cached_signatures': 0, 'cached_content_hashes': 0, 'tracked_chats': 0, 'last_cleanup': 0},
                'enabled_features': []
            }
    
    def _get_enabled_features(self, config: Dict[str, Any]) -> List[str]:
        """获取启用的功能列表"""
        features = []
        if config.get('enable_time_window'): features.append("时间窗口")
        if config.get('enable_content_hash'): features.append("内容哈希")
        if config.get('enable_smart_similarity'): features.append("智能相似度")
        return features
    
    async def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新去重配置"""
        try:
            await smart_deduplicator.update_config(updates)
            
            return {
                'success': True,
                'message': '配置更新成功',
                'updated_config': smart_deduplicator.config
            }
            
        except Exception as e:
            logger.error(f"更新去重配置失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def toggle_feature(self, feature: str, enabled: bool) -> Dict[str, Any]:
        """切换功能开关"""
        feature_mapping = {
            'time_window': 'enable_time_window',
            'content_hash': 'enable_content_hash',
            'smart_similarity': 'enable_smart_similarity'
        }
        
        if feature not in feature_mapping:
            return {'success': False, 'error': f'未知功能: {feature}'}
        
        config_key = feature_mapping[feature]
        return await self.update_config({config_key: enabled})
    
    async def set_time_window(self, hours: int) -> Dict[str, Any]:
        """设置时间窗口（支持永久：传入0或负数视为永久）"""
        # 0 或负数表示永久
        if hours <= 0:
            return await self.update_config({'time_window_hours': 0})
        # 合理范围限制仍保留
        if hours < 1 or hours > 168:  # 1小时到7天
            return {'success': False, 'error': '时间窗口必须在1-168小时之间，或设置为0表示永久'}
        return await self.update_config({'time_window_hours': hours})
    
    async def set_similarity_threshold(self, threshold: float) -> Dict[str, Any]:
        """设置相似度阈值"""
        if threshold < 0.5 or threshold > 1.0:
            return {'success': False, 'error': '相似度阈值必须在0.5-1.0之间'}
        
        return await self.update_config({'similarity_threshold': threshold})
    
    async def set_cleanup_interval(self, interval_seconds: int) -> Dict[str, Any]:
        """设置清理间隔"""
        if interval_seconds < 300 or interval_seconds > 86400:  # 5分钟到24小时
            return {'success': False, 'error': '清理间隔必须在300-86400秒之间'}
        
        return await self.update_config({'cache_cleanup_interval': interval_seconds})
    
    async def manual_cleanup(self) -> Dict[str, Any]:
        """手动清理缓存"""
        try:
            # 获取清理前统计
            stats_before = smart_deduplicator.get_stats()
            
            # 强制清理
            smart_deduplicator.last_cleanup = 0
            await smart_deduplicator._cleanup_cache_if_needed()
            
            # 获取清理后统计
            stats_after = smart_deduplicator.get_stats()
            
            return {
                'success': True,
                'message': '缓存清理完成',
                'stats': {
                    'before': {
                        'signatures': stats_before.get('cached_signatures', 0),
                        'hashes': stats_before.get('cached_content_hashes', 0)
                    },
                    'after': {
                        'signatures': stats_after.get('cached_signatures', 0),
                        'hashes': stats_after.get('cached_content_hashes', 0)
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"手动清理缓存失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def clear_all_cache(self) -> Dict[str, Any]:
        """清空所有缓存"""
        try:
            # 获取清空前统计
            stats_before = smart_deduplicator.get_stats()
            
            # 清空缓存
            smart_deduplicator.time_window_cache.clear()
            smart_deduplicator.content_hash_cache.clear()
            
            return {
                'success': True,
                'message': '所有缓存已清空',
                'cleared_items': {
                    'signatures': stats_before.get('cached_signatures', 0),
                    'hashes': stats_before.get('cached_content_hashes', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def reset_to_defaults(self) -> Dict[str, Any]:
        """重置为默认配置"""
        try:
            await smart_deduplicator.reset_to_defaults()
            
            return {
                'success': True,
                'message': '配置已重置为默认值',
                'config': smart_deduplicator.config
            }
            
        except Exception as e:
            logger.error(f"重置配置失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """获取去重统计数据"""
        return smart_deduplicator.get_stats()

    async def get_details(self) -> Dict[str, Any]:
        """获取完整详情数据供渲染使用"""
        config = smart_deduplicator.config
        if not smart_deduplicator._config_loaded:
            await smart_deduplicator.load_config()
            config = smart_deduplicator.config

        return {
            'config': config,
            'stats': smart_deduplicator.get_stats(),
            'enabled_features': self._get_enabled_features(config)
        }

    async def dispatch_config_update(self, action: str, extra_data: List[str] = None) -> Tuple[bool, str]:
        """统一配置更新调度器 (核心逻辑下沉)"""
        try:
            key = None
            value = None
            msg = "✅ 配置已更新"
            
            # Action Mapping
            if action == "toggle_similarity":
                key = "enable_smart_similarity"
                value = extra_data[0] == "True"
            elif action == "set_similarity":
                key = "similarity_threshold"
                value = float(extra_data[0])
            elif action == "toggle_content_hash":
                key = "enable_content_hash"
                value = extra_data[0] == "True"
            elif action == "toggle_video_file_id":
                key = "enable_video_file_id_check"
                value = extra_data[0] == "True"
            elif action == "toggle_video_partial":
                key = "enable_video_partial_hash_check"
                value = extra_data[0] == "True"
            elif action == "toggle_time_window":
                key = "enable_time_window"
                value = extra_data[0] == "True"
            elif action == "set_time_window":
                key = "time_window_hours"
                value = int(extra_data[0])
            elif action == "toggle_sticker_filter":
                key = "enable_sticker_filter"
                value = extra_data[0] == "True"
            elif action == "toggle_sticker_strict":
                key = "sticker_strict_mode"
                value = extra_data[0] == "True"
            elif action == "toggle_global_search":
                key = "enable_global_search"
                value = extra_data[0] == "True"
            elif action == "toggle_album_dedup":
                key = "enable_album_dedup"
                value = extra_data[0] == "True"
            elif action == "set_album_threshold":
                key = "album_duplicate_threshold"
                value = float(extra_data[0])
            elif action == "manual_cleanup":
                await smart_deduplicator._flush_buffer()
                smart_deduplicator.time_window_cache.clear()
                smart_deduplicator.content_hash_cache.clear()
                return True, "✅ 缓存已手动清理"
            elif action == "reset_dedup_config":
                await smart_deduplicator.reset_to_defaults()
                return True, "✅ 已重置为默认配置"

            if key:
                await smart_deduplicator.update_config({key: value})
                return True, msg
                
            return False, "⚠️ 未知动作"
        except Exception as e:
            logger.error(f"Dispatch config update failed: {e}")
            return False, f"❌ 更新失败: {str(e)}"
    
    async def get_hash_examples(self) -> Dict[str, Any]:
        """获取哈希示例"""
        return {
            'text_example': {
                'original': '今天天气真好！🌞 https://example.com',
                'cleaned': '今天天气真好',
                'hash': '5d41402abc4b2a76b9719d911017c592'
            },
            'photo_example': {
                'features': 'type:photo|size:1920x1080',
                'hash': 'a1b2c3d4e5f6789012345678901234ab'
            },
            'document_example': {
                'features': 'type:document|size_range:medium|mime:application/pdf',
                'hash': '9f8e7d6c5b4a39281726354098765432'
            },
            'advantages': [
                '忽略时间戳、链接等变化部分',
                '基于实际内容与媒体特征的感知哈希 (V3)',
                '极速 XXH128 哈希算法，零碰撞风险'
            ]
        }
    
    async def is_duplicate(self, chat_id: int, message_obj, rule_config: Dict = None) -> bool:
        """
        检查消息是否重复
        复用 services.dedup.engine 中的智能去重逻辑
        """
        # 1. 使用智能去重器检查重复
        # ✅ 使用全局实例，利用内存缓存
        is_dup, reason = await smart_deduplicator.check_duplicate(
            message_obj,
            chat_id,
            rule_config=rule_config,
            readonly=True  # 只读模式，不记录新消息到缓存
        )
        
        if is_dup:
            await self._on_duplicate_found(chat_id, message_obj, reason)
            return True
        
        return False

    async def _on_duplicate_found(self, chat_id: int, message_obj, reason: str, rule_id: int = None):
        """当发现重复消息时的统一处理逻辑"""
        logger.info(f"🚫 [Dedup] Duplicate found in chat {chat_id}: {reason}")
        try:
            # 1. 计算并记录节省流量
            size = self._get_message_size(message_obj)
            if size > 0:
                await self.stats_repo.increment_stats(chat_id, saved_bytes=size)
            
            # 2. 如果提供了规则ID，更新规则统计
            if rule_id:
                await self.stats_repo.increment_rule_stats(rule_id, status="filtered")
                
                # 3. 记录过滤日志 (可选，考虑到性能和存储，这里选择记录)
                from core.helpers.msg_utils import detect_message_type
                msg_type = detect_message_type(message_obj)
                msg_text = getattr(message_obj, 'text', '') or getattr(message_obj, 'raw_text', '')
                
                await self.stats_repo.log_action(
                    rule_id=rule_id,
                    msg_id=getattr(message_obj, 'id', 0),
                    status="filtered",
                    result=f"Duplicate: {reason}",
                    msg_text=msg_text,
                    msg_type=msg_type
                )
        except Exception as e:
            logger.warning(f"Failed to record duplicate stats: {e}")

    def _get_message_size(self, message) -> int:
        """获取消息大小(字节)"""
        try:
            # 优先从 file 属性获取 (Telethon Message)
            if hasattr(message, "file") and message.file:
                return int(getattr(message.file, "size", 0) or 0)
            # 文本消息计算长度
            text = getattr(message, 'text', '') or getattr(message, 'raw_text', '')
            if text:
                return len(str(text))
        except Exception as e:
            try:
                message_id = getattr(message, "id", "unknown")
            except Exception:
                message_id = "unknown"
            logger.warning(
                "Failed to get message size for message_id=%s: %s",
                message_id,
                e,
            )
        return 0
        
    async def check_and_lock(self, chat_id: int, message_obj, rule_config: Dict = None, rule_id: int = None) -> Tuple[bool, str]:
        """
        [Transaction Start] 乐观去重检查 + 锁定
        """
        is_dup, reason = await smart_deduplicator.check_duplicate(
            message_obj,
            chat_id,
            rule_config=rule_config,
            readonly=False
        )
        
        if is_dup:
            await self._on_duplicate_found(chat_id, message_obj, reason, rule_id=rule_id)
            
        return is_dup, reason

    # Alias for backward compatibility (Deprecated)
    check_and_record = check_and_lock
        
    async def rollback(self, chat_id: int, message_obj):
        """回滚去重状态 (删除记录)"""
        await smart_deduplicator.remove_message(message_obj, chat_id)
    
    async def record_signature(self, chat_id, message_obj):
        """记录签名 (供 EventBus 调用)"""
        try:
            # 1. 使用智能去重器记录消息
            # ✅ 使用全局实例，利用内存缓存
            
            # 生成签名和内容哈希
            from services.dedup import tools
            signature = tools.generate_signature(message_obj)
            content_hash = tools.generate_content_hash(message_obj)
            
            # [Bloom Filter] 更新布隆过滤器
            if signature:
                bloom_filter_service.add(signature)

            # 记录消息到缓存和数据库
            await smart_deduplicator.record_message(message_obj, chat_id, signature, content_hash)
            
            logger.debug(f"Recorded signature for chat {chat_id}, message_id {message_obj.id}")
            
            # 2. 同时记录到 MediaSignature 表（兼容现有系统）
            if message_obj.media:
                file_id = getattr(message_obj, 'file', None)
                if file_id:
                    sig = str(file_id.id)
                    media_type = getattr(message_obj.media, '__class__.__name__', 'unknown')
                    
                    if self.coordinator:
                        # [Group Commit] 使用缓冲区异步写入
                        from datetime import datetime
                        now = datetime.utcnow().isoformat()
                        
                        new_signature = MediaSignature(
                            chat_id=str(chat_id),
                            signature=sig,
                            file_id=str(file_id.id),
                            content_hash=content_hash,
                            media_type=media_type,
                            count=1,
                            created_at=now,
                            updated_at=now,
                            last_seen=now
                        )
                        await self.coordinator.buffer.add(new_signature)
                        logger.debug(f"Buffered signature for DB: {sig} in {chat_id}")
                    else:
                        # Use Repository for sync/immediate commit
                        await self.repo.add_or_update(
                            chat_id=str(chat_id),
                            signature=sig,
                            file_id=str(file_id.id),
                            content_hash=content_hash,
                            media_type=media_type,
                            # message_id=message_obj.id  # MediaSignature 模型不支持此参数
                        )
                        logger.debug(f"Recorded signature via Repo: {sig} in {chat_id}")
        except Exception as e:
            logger.error(f"Failed to record signature: {e}", exc_info=True)
    
    async def commit(self, target_chat_id: int, message_obj):
        """
        [Transaction Commit] 最终确认
        将去重记录写入持久化数据库 (Commit).
        仅在发送成功后调用。
        """
        try:
            # 复用现有的 record_signature 逻辑 (写入 DB)
            await self.record_signature(target_chat_id, message_obj)
        except Exception as e:
            logger.error(f"Error committing dedup signature: {e}", exc_info=True)

    # Alias for backward compatibility (Deprecated)
    record_message = commit
    
    async def on_forward_success(self, event_data: dict):
        """
        [Callback] 处理转发成功事件
        event_data 结构参考 SenderMiddleware:
        {
            "rule_id": rule.id,
            "msg_id": ctx.message_id,
            "target_id": target_id,
            ...
        }
        """
        try:
            # 注意：此处可能无法直接获取完整的 message_obj
            # 因为事件数据中只包含 ID 信息
            # 实际的去重记录已经在 SenderMiddleware 中完成
            logger.debug(f"Received FORWARD_SUCCESS event: {event_data}")
            
            # 这里可以添加一些额外的去重逻辑，或者记录统计信息
        except Exception as e:
            logger.error(f"Dedup write-back failed: {e}", exc_info=True)
    
    def set_db(self, db):
        """设置数据库连接"""
        self.db = db

# 全局服务实例
dedup_service = DeduplicationService()
