"""
规则管理服务层 (原生异步版)
专门处理转发规则的增删改查业务逻辑
"""
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
from sqlalchemy import select, func, cast, String, delete
from sqlalchemy.orm import aliased, selectinload

from utils.core.error_handler import handle_errors, log_execution
from models.models import ForwardRule, Chat, Keyword, ReplaceRule, MediaTypes, MediaExtensions, RuleSync
from services.rule_service import RuleQueryService
from enums.enums import ForwardMode, AddMode
import json
try:
    import yaml
except ImportError:
    yaml = None

# 导入container实例 (移至方法内以避免循环导入)
# from core.container import container

logger = logging.getLogger(__name__)

class RuleManagementService:
    """转发规则管理业务逻辑服务"""
    
    @property
    def container(self):
        from core.container import container
        return container
    
    @handle_errors(default_return={'rules': [], 'total': 0, 'page': 0, 'page_size': 10})
    @log_execution()
    async def get_rule_list(self, page: int = 0, page_size: int = 10, search_query: str = None) -> Dict[str, Any]:
        """获取规则列表 (原生异步)"""
        async with self.container.db.session() as session:
            SourceChat = aliased(Chat)
            TargetChat = aliased(Chat)
            
            # 构建基础查询
            stmt = select(ForwardRule).outerjoin(
                SourceChat, ForwardRule.source_chat_id == SourceChat.id
            ).outerjoin(
                TargetChat, ForwardRule.target_chat_id == TargetChat.id
            ).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat),
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules)
            )
            
            # 搜索过滤
            if search_query:
                stmt = stmt.filter(
                    cast(ForwardRule.id, String).like(f'%{search_query}%')
                )
            
            # 计算总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = (await session.execute(count_stmt)).scalar() or 0
            
            # 分页
            stmt = stmt.offset(page * page_size).limit(page_size)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            
            # 转换为数据格式
            rules_data = []
            for rule in rules:
                def _serialize_chat(chat):
                    if not chat:
                        return {'title': 'Unknown', 'telegram_chat_id': 'Unknown'}
                    title = getattr(chat, 'title', None) or getattr(chat, 'name', None)
                    if not title:
                        title = f"Chat {getattr(chat, 'telegram_chat_id', '')}"
                    return {
                        'title': str(title),
                        'telegram_chat_id': str(getattr(chat, 'telegram_chat_id', 'Unknown')),
                        'id': getattr(chat, 'id', None)
                    }
                
                rule_data = {
                    'id': rule.id,
                    'name': f"规则 {rule.id}",
                    'source_chat': _serialize_chat(rule.source_chat),
                    'target_chat': _serialize_chat(rule.target_chat),
                    'enabled': getattr(rule, 'enable_rule', True),
                    'created_at': rule.created_at if hasattr(rule, 'created_at') and rule.created_at else None,
                    'keywords_count': len(getattr(rule, 'keywords', [])),
                    'replace_rules_count': len(getattr(rule, 'replace_rules', [])),
                    'forward_mode': getattr(rule, 'forward_mode', None),
                    'is_ai': getattr(rule, 'is_ai', False),
                    'is_summary': getattr(rule, 'is_summary', False),
                }
                rules_data.append(rule_data)
            
            return {
                'rules': rules_data,
                'total': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
            }
    
    @handle_errors(default_return={'success': False, 'error': 'Rule not found'})
    async def get_rule_detail(self, rule_id: int) -> Dict[str, Any]:
        """获取规则详情 (原生异步)"""
        async with self.container.db.session() as session:
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat),
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules)
            ).filter_by(id=rule_id)
            
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            if not rule:
                return {'success': False, 'error': '规则不存在'}
            
            def _serialize_chat(chat):
                if not chat:
                    return {'title': 'Unknown', 'telegram_chat_id': 'Unknown'}
                title = getattr(chat, 'title', None) or getattr(chat, 'name', None)
                if not title:
                    title = f"Chat {getattr(chat, 'telegram_chat_id', '')}"
                return {
                    'title': str(title),
                    'telegram_chat_id': str(getattr(chat, 'telegram_chat_id', 'Unknown')),
                    'id': getattr(chat, 'id', None)
                }
            
            # 提取关键词列表
            keywords = [k.keyword for k in getattr(rule, 'keywords', [])]
            
            # 提取替换规则列表
            replace_rules = []
            for rr in getattr(rule, 'replace_rules', []):
                replace_rules.append({
                    'pattern': rr.pattern,
                    'replacement': rr.content,
                    'is_regex': rr.is_regex
                })
            
            return {
                'success': True,
                'id': rule.id,
                'source_chat': _serialize_chat(rule.source_chat),
                'target_chat': _serialize_chat(rule.target_chat),
                'enabled': getattr(rule, 'enable_rule', True),
                'forward_mode': getattr(rule, 'forward_mode', None),
                'keywords': keywords,
                'keywords_count': len(keywords),
                'replace_rules': replace_rules,
                'replace_rules_count': len(replace_rules),
                'settings': { # Add settings structure for detail view
                    'enabled': getattr(rule, 'enable_rule', True),
                    'enable_dedup': getattr(rule, 'enable_dedup', False),
                    'dedup_time_window_hours': 24, # Default or fetch from config if needed, simple default for now
                    'similarity_threshold': 0.85
                },
                'is_ai': getattr(rule, 'is_ai', False),
                'is_summary': getattr(rule, 'is_summary', False),
                'enable_dedup': getattr(rule, 'enable_dedup', False),
                'created_at': getattr(rule, 'created_at', None),
                'use_bot': getattr(rule, 'use_bot', True),
                'handle_mode': getattr(rule, 'handle_mode', 'forward'),
                'is_delete_original': getattr(rule, 'is_delete_original', False),
                'message_mode': getattr(rule, 'message_mode', 'MARKDOWN'),
                'is_preview': getattr(rule, 'is_preview', 'ENABLE'),
                'is_original_sender': getattr(rule, 'is_original_sender', True),
                'is_original_time': getattr(rule, 'is_original_time', True),
                'is_original_link': getattr(rule, 'is_original_link', True),
                'is_filter_user_info': getattr(rule, 'is_filter_user_info', False),
                'enable_comment_button': getattr(rule, 'enable_comment_button', False),
                'enable_delay': getattr(rule, 'enable_delay', False),
                'delay_seconds': getattr(rule, 'delay_seconds', 0),
                'force_pure_forward': getattr(rule, 'force_pure_forward', False),
                'enable_sync': getattr(rule, 'enable_sync', False)
            }
    
    @handle_errors(default_return={'success': False, 'error': 'Rule creation failed'})
    async def create_rule(self, source_chat_id: str, target_chat_id: str, **settings) -> Dict[str, Any]:
        """创建新规则 (原生异步)"""
        from utils.helpers.id_utils import get_display_name_async
        source_display = await get_display_name_async(source_chat_id)
        target_display = await get_display_name_async(target_chat_id)
        logger.info(f"[RuleService] 开始创建规则: 来源={source_display}({source_chat_id}), 目标={target_display}({target_chat_id}), 设置={settings}")
        
        try:
            async with self.container.db.session() as session:
                # 验证源聊天和目标聊天是否存在
                s_stmt = select(Chat).filter_by(telegram_chat_id=str(source_chat_id))
                t_stmt = select(Chat).filter_by(telegram_chat_id=str(target_chat_id))
                
                source_chat = (await session.execute(s_stmt)).scalar_one_or_none()
                target_chat = (await session.execute(t_stmt)).scalar_one_or_none()
                
                if not source_chat:
                    error_msg = f'源聊天 {source_chat_id} 不存在，请先添加该聊天'
                    logger.error(f"[RuleService] 规则创建失败: {error_msg}")
                    return {'success': False, 'error': error_msg}
                
                if not target_chat:
                    error_msg = f'目标聊天 {target_chat_id} 不存在，请先添加该聊天'
                    logger.error(f"[RuleService] 规则创建失败: {error_msg}")
                    return {'success': False, 'error': error_msg}
                    
                # 创建新规则
                new_rule = ForwardRule(
                    source_chat_id=source_chat.id,
                    target_chat_id=target_chat.id,
                    enable_rule=settings.get('enable_rule', True),
                    enable_dedup=settings.get('enable_dedup', False),
                    forward_mode=settings.get('forward_mode', ForwardMode.BLACKLIST),
                    created_at=datetime.utcnow()
                )
                
                # 添加其他设置
                for key, value in settings.items():
                    if key not in ['enable_rule', 'enable_dedup', 'forward_mode'] and hasattr(new_rule, key):
                        setattr(new_rule, key, value)
                
                session.add(new_rule)
                await session.commit()
                await session.refresh(new_rule)
                
                logger.info(f"[RuleService] 规则创建成功，ID={new_rule.id}")
                return {'success': True, 'rule_id': new_rule.id}
                
        except Exception as e:
            from utils.helpers.id_utils import get_display_name_async
            source_display = await get_display_name_async(source_chat_id)
            target_display = await get_display_name_async(target_chat_id)
            logger.error(f"[RuleService] 规则创建失败: 来源={source_display}({source_chat_id}), 目标={target_display}({target_chat_id}), 错误={e}", exc_info=True)
            return {'success': False, 'error': f'规则创建失败: {str(e)}'}
    
    @handle_errors(default_return={'success': False, 'error': 'Rule update failed'})
    @log_execution()
    async def update_rule(self, rule_id: int, **settings) -> Dict[str, Any]:
        """更新规则设置 (原生异步)"""
        logger.info(f"[RuleService] 开始更新规则: ID={rule_id}, 设置={settings}")
        
        try:
            async with self.container.db.session() as session:
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat)
                ).filter_by(id=rule_id)
                result = await session.execute(stmt)
                rule = result.scalar_one_or_none()
                
                if not rule:
                    error_msg = f'规则 {rule_id} 不存在'
                    logger.error(f"[RuleService] 规则更新失败: {error_msg}")
                    return {'success': False, 'error': error_msg}
                
                # 保存原始聊天ID用于清除缓存
                original_source_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
                original_target_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
                
                # 更新规则设置
                for key, value in settings.items():
                    if hasattr(rule, key):
                        old_value = getattr(rule, key)
                        if old_value != value:
                            setattr(rule, key, value)
                            logger.debug(f"[RuleService] 规则 {rule_id} 更新字段: {key} = {value} (旧值: {old_value})")
                
                if hasattr(rule, 'updated_at'):
                    rule.updated_at = datetime.now().isoformat()
                    logger.debug(f"[RuleService] 规则 {rule_id} 更新时间戳")
                
                await session.commit()
                result = {'success': True, 'message': '规则更新成功', 'source_chat_id': original_source_id, 'target_chat_id': original_target_id}
                
                # 清除相关缓存 (Unified)
                if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
                    self.container.rule_repo.clear_cache(result['source_chat_id'])
                    self.container.rule_repo.clear_cache(result['target_chat_id'])
                    logger.info(f"[RuleService] 清除规则缓存: 源ChatID={result['source_chat_id']}, 目标ChatID={result['target_chat_id']}")
                
                logger.info(f"[RuleService] 规则更新成功，ID={rule_id}")
                return result
                
        except Exception as e:
            logger.error(f"[RuleService] 规则更新失败: ID={rule_id}, 设置={settings}, 错误={e}", exc_info=True)
            return {'success': False, 'error': f'规则更新失败: {str(e)}'}
    
    @handle_errors(default_return={'success': False, 'error': 'Rule deletion failed'})
    @log_execution()
    async def delete_rule(self, rule_id: int) -> Dict[str, Any]:
        """删除规则 (原生异步)"""
        logger.info(f"[RuleService] 开始删除规则: ID={rule_id}")
        
        try:
            async with self.container.db.session() as session:
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat)
                ).filter_by(id=rule_id)
                result = await session.execute(stmt)
                rule = result.scalar_one_or_none()
                
                if not rule:
                    error_msg = f'规则 {rule_id} 不存在'
                    logger.error(f"[RuleService] 规则删除失败: {error_msg}")
                    return {'success': False, 'error': error_msg}
                
                # 保存聊天ID用于清除缓存
                source_chat_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
                target_chat_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
                
                # 记录要删除的规则详情
                source_name = rule.source_chat.name if rule.source_chat else '未知'
                target_name = rule.target_chat.name if rule.target_chat else '未知'
                logger.debug(f"[RuleService] 准备删除规则: ID={rule_id}, 来源={source_name} ({source_chat_id}), 目标={target_name} ({target_chat_id})")
                
                await session.delete(rule)
                await session.commit()
                logger.info(f"[RuleService] 规则删除成功: ID={rule_id}")
                
                result = {'success': True, 'message': '规则删除成功', 'source_chat_id': source_chat_id, 'target_chat_id': target_chat_id}
            
            # 清除相关缓存 (Unified)
            if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
                self.container.rule_repo.clear_cache(result['source_chat_id'])
                self.container.rule_repo.clear_cache(result['target_chat_id'])
                logger.info(f"[RuleService] 清除规则缓存: 源ChatID={result['source_chat_id']}, 目标ChatID={result['target_chat_id']}")
            
            return result
            
        except Exception as e:
            logger.error(f"[RuleService] 规则删除失败: ID={rule_id}, 错误={e}", exc_info=True)
            return {'success': False, 'error': f'规则删除失败: {str(e)}'}
    
    async def toggle_rule_status(self, rule_id: int, enabled: bool) -> Dict[str, Any]:
        """切换规则启用状态"""
        status = "启用" if enabled else "禁用"
        logger.info(f"[RuleService] 开始{status}规则: ID={rule_id}")
        
        try:
            # 规则模型字段为 enable_rule，这里保持一致
            result = await self.update_rule(rule_id, enable_rule=enabled)
            
            if result.get('success'):
                logger.info(f"[RuleService] 规则{status}成功: ID={rule_id}")
            else:
                logger.error(f"[RuleService] 规则{status}失败: ID={rule_id}, 错误={result.get('error')}")
            
            return result
        except Exception as e:
            logger.error(f"[RuleService] 规则{status}失败: ID={rule_id}, 错误={e}", exc_info=True)
            return {'success': False, 'error': f'规则{status}失败: {str(e)}'}

    @handle_errors(default_return={'success': False, 'error': 'Toggle failed'})
    async def toggle_rule_boolean_setting(self, rule_id: int, key: str) -> Dict[str, Any]:
        """通用切换规则布尔设置"""
        # 映射字段名（如果 UI 使用的 key 与模型字段不完全一致）
        field_map = {
            'enabled': 'enable_rule',
            'is_preview': 'is_preview',  # 注意：is_preview 在模型中是 Enum(PreviewMode)，这里需要特殊处理
            'is_delete_original': 'is_delete_original',
            'is_original_sender': 'is_original_sender',
            'is_original_time': 'is_original_time',
            'is_original_link': 'is_original_link',
            'is_filter_user_info': 'is_filter_user_info',
            'enable_comment_button': 'enable_comment_button',
            'enable_dedup': 'enable_dedup',
            'enable_delay': 'enable_delay',
            'force_pure_forward': 'force_pure_forward',
            'enable_sync': 'enable_sync',
            'use_bot': 'use_bot'
        }
        
        real_key = field_map.get(key, key)
        
        async with self.container.db.session() as session:
            from sqlalchemy.orm import selectinload
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            if not rule:
                return {'success': False, 'error': '规则不存在'}
            
            # 特殊处理 Enum
            if key == 'forward_mode':
                from enums.enums import ForwardMode
                modes = [ForwardMode.BLACKLIST, ForwardMode.WHITELIST, ForwardMode.BLACKLIST_THEN_WHITELIST, ForwardMode.WHITELIST_THEN_BLACKLIST]
                current = rule.forward_mode
                next_mode = modes[(modes.index(current) + 1) % len(modes)]
                rule.forward_mode = next_mode
            elif key == 'handle_mode':
                from enums.enums import HandleMode
                modes = [HandleMode.FORWARD, HandleMode.EDIT]
                current = rule.handle_mode
                next_mode = modes[(modes.index(current) + 1) % len(modes)]
                rule.handle_mode = next_mode
            elif key == 'message_mode':
                from enums.enums import MessageMode
                modes = [MessageMode.MARKDOWN, MessageMode.HTML, MessageMode.TEXT]
                current = rule.message_mode
                next_mode = modes[(modes.index(current) + 1) % len(modes)]
                rule.message_mode = next_mode
            elif key == 'is_preview':
                from enums.enums import PreviewMode
                modes = [PreviewMode.ENABLE, PreviewMode.DISABLE, PreviewMode.FOLLOW]
                current = rule.is_preview
                next_mode = modes[(modes.index(current) + 1) % len(modes)]
                rule.is_preview = next_mode
            else:
                # 普通布尔值
                if hasattr(rule, real_key):
                    current = getattr(rule, real_key)
                    setattr(rule, real_key, not current)
                else:
                    return {'success': False, 'error': f'无效字段: {key}'}
            
            await session.commit()
            
            # 清除缓存
            if rule.source_chat:
                self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
            if rule.target_chat:
                self.container.rule_repo.clear_cache(int(rule.target_chat.telegram_chat_id))
                
            return {'success': True}
    
    @handle_errors(default_return={'success': False, 'error': 'Rule copy failed'})
    @log_execution()
    async def copy_rule(self, source_rule_id: int, target_rule_id: Optional[int] = None) -> Dict[str, Any]:
        """复制规则配置到目标规则 (原生异步)"""
        from sqlalchemy import inspect
        async with self.container.db.session() as session:
            # 查询源规则，包含所有关联数据
            source_stmt = select(ForwardRule).options(
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules),
                selectinload(ForwardRule.media_types),
                selectinload(ForwardRule.media_extensions),
                selectinload(ForwardRule.rule_syncs),
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=source_rule_id)
            source_result = await session.execute(source_stmt)
            source_rule = source_result.scalar_one_or_none()
            
            if not source_rule:
                return {'success': False, 'error': '源规则不存在'}
            
            # 获取目标规则
            if not target_rule_id:
                return {'success': False, 'error': '必须指定目标规则ID'}
            
            # 查询目标规则，包含所有关联数据
            target_stmt = select(ForwardRule).options(
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules),
                selectinload(ForwardRule.media_types),
                selectinload(ForwardRule.media_extensions),
                selectinload(ForwardRule.rule_syncs),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=target_rule_id)
            target_result = await session.execute(target_stmt)
            target_rule = target_result.scalar_one_or_none()
            
            if not target_rule:
                return {'success': False, 'error': f'目标规则 {target_rule_id} 不存在'}
            
            # 统计变量
            stats = {
                "kw_norm": {"ok": 0, "skip": 0},
                "kw_regex": {"ok": 0, "skip": 0},
                "replace": {"ok": 0, "skip": 0},
                "ext": {"ok": 0, "skip": 0},
                "sync": {"ok": 0, "skip": 0},
            }
            
            # 1. 复制关键字
            existing_keywords = {
                (k.keyword, k.is_regex, k.is_blacklist) for k in target_rule.keywords
            }
            for kw in source_rule.keywords:
                key = (kw.keyword, kw.is_regex, kw.is_blacklist)
                if key not in existing_keywords:
                    new_kw = Keyword(
                        rule_id=target_rule.id,
                        keyword=kw.keyword,
                        is_regex=kw.is_regex,
                        is_blacklist=kw.is_blacklist
                    )
                    session.add(new_kw)
                    existing_keywords.add(key)
                    if kw.is_regex:
                        stats["kw_regex"]["ok"] += 1
                    else:
                        stats["kw_norm"]["ok"] += 1
                else:
                    if kw.is_regex:
                        stats["kw_regex"]["skip"] += 1
                    else:
                        stats["kw_norm"]["skip"] += 1
            
            # 2. 复制替换规则
            existing_replaces = {
                (r.pattern, r.content) for r in target_rule.replace_rules
            }
            for rr in source_rule.replace_rules:
                key = (rr.pattern, rr.content)
                if key not in existing_replaces:
                    new_rr = ReplaceRule(
                        rule_id=target_rule.id,
                        pattern=rr.pattern,
                        content=rr.content,
                        is_regex=rr.is_regex
                    )
                    session.add(new_rr)
                    existing_replaces.add(key)
                    stats["replace"]["ok"] += 1
                else:
                    stats["replace"]["skip"] += 1
            
            # 3. 复制媒体扩展名
            existing_exts = {
                ext.extension for ext in target_rule.media_extensions
            }
            for ext in source_rule.media_extensions:
                if ext.extension not in existing_exts:
                    new_ext = MediaExtensions(
                        rule_id=target_rule.id,
                        extension=ext.extension,
                    )
                    session.add(new_ext)
                    existing_exts.add(ext.extension)
                    stats["ext"]["ok"] += 1
                else:
                    stats["ext"]["skip"] += 1
            
            # 4. 复制媒体类型 (1对1关系)
            if source_rule.media_types:
                # 检查目标是否已有 media_types
                stmt_mt = select(MediaTypes).where(MediaTypes.rule_id == target_rule.id)
                target_media_types = (
                    await session.execute(stmt_mt)
                ).scalar_one_or_none()

                if not target_media_types:
                    target_media_types = MediaTypes(rule_id=target_rule.id)
                    session.add(target_media_types)

                # 复制属性
                inspector = inspect(MediaTypes)
                for column in inspector.columns:
                    if column.key not in ["id", "rule_id"]:
                        setattr(
                            target_media_types,
                            column.key,
                            getattr(source_rule.media_types, column.key),
                        )
            
            # 5. 复制同步规则
            existing_syncs = {
                sync.sync_rule_id for sync in target_rule.rule_syncs
            }
            for sync in source_rule.rule_syncs:
                if (
                    sync.sync_rule_id != target_rule.id
                    and sync.sync_rule_id not in existing_syncs
                ):
                    new_sync = RuleSync(
                        rule_id=target_rule.id,
                        sync_rule_id=sync.sync_rule_id
                    )
                    session.add(new_sync)
                    existing_syncs.add(sync.sync_rule_id)
                    stats["sync"]["ok"] += 1
                    target_rule.enable_sync = True
                else:
                    stats["sync"]["skip"] += 1
            
            # 6. 复制基础设置 (排除关联字段)
            inspector = inspect(ForwardRule)
            skip_cols = [
                "id",
                "source_chat_id",
                "target_chat_id",
                "source_chat",
                "target_chat",
                "keywords",
                "replace_rules",
                "media_types",
                "media_extensions",
                "rule_syncs",
            ]
            for column in inspector.columns:
                if column.key not in skip_cols:
                    setattr(target_rule, column.key, getattr(source_rule, column.key))
            
            # 返回结果
            result = {
                'success': True, 
                'message': '规则复制成功',
                'target_rule_id': target_rule.id,
                'source_chat_id': int(source_rule.source_chat.telegram_chat_id),
                'target_chat_id': int(target_rule.target_chat.telegram_chat_id),
                'stats': stats
            }
            
            await session.commit()
            logger.info(f"[RuleService] 规则复制提交成功，目标ID={target_rule.id}")
        
        # 清除相关缓存 (Unified)
        if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
            self.container.rule_repo.clear_cache(result['source_chat_id'])
            self.container.rule_repo.clear_cache(result['target_chat_id'])
        
        return result
    
    @handle_errors(default_return={'success': False, 'error': 'Failed to get chat list', 'chats': []})
    @log_execution()
    async def get_chat_list(self) -> Dict[str, Any]:
        """获取可用的聊天列表 (原生异步)"""
        async with self.container.db.session() as session:
            stmt = select(Chat)
            result = await session.execute(stmt)
            chats = result.scalars().all()
            
            chat_list = []
            for chat in chats:
                chat_list.append({
                    'id': chat.id,
                    'telegram_chat_id': chat.telegram_chat_id,
                    'title': (getattr(chat, 'name', None) or getattr(chat, 'title', None) or f'Chat {chat.telegram_chat_id}'),
                    'type': getattr(chat, 'type', 'unknown')
                })
            
            return {'success': True, 'chats': chat_list}
    
    @handle_errors(default_return={'success': False, 'error': 'Failed to add keywords'})
    @log_execution()
    async def add_keywords(self, rule_id: int, keywords: List[str], is_regex: bool = False, is_negative: bool = False, case_sensitive: bool = False) -> Dict[str, Any]:
        """添加关键字到规则 (原生异步)处理"""
        async with self.container.db.session() as session:
            # 获取规则信息
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            if not rule:
                return {'success': False, 'error': '规则不存在'}
            
            # 保存聊天ID用于清除缓存
            source_chat_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
            target_chat_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
            
            # 1. 批量查询已存在的关键字
            existing_stmt = select(Keyword.keyword).filter(
                Keyword.rule_id == rule_id,
                Keyword.keyword.in_(keywords),
                Keyword.is_regex == is_regex,
                Keyword.is_blacklist == is_negative
            )
            existing_result = await session.execute(existing_stmt)
            existing_keywords = set(existing_result.scalars().all())
            
            # 2. 筛选出真正需要新增的关键字
            new_keywords = [k for k in keywords if k not in existing_keywords]
            
            # 3. 批量添加新关键字
            if new_keywords:
                new_keyword_objects = [
                    Keyword(
                        rule_id=rule_id,
                        keyword=k,
                        is_regex=is_regex,
                        is_blacklist=is_negative
                    ) for k in new_keywords
                ]
                session.add_all(new_keyword_objects)
            
            await session.commit()
            result = {
                'success': True,
                'message': f'关键字添加成功，新增 {len(new_keywords)} 个，跳过 {len(keywords) - len(new_keywords)} 个重复项',
                'source_chat_id': source_chat_id,
                'target_chat_id': target_chat_id
            }
        
        # 清除相关缓存 (Unified)
        if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
            self.container.rule_repo.clear_cache(result['source_chat_id'])
            self.container.rule_repo.clear_cache(result['target_chat_id'])
        
        return result
    
    @handle_errors(default_return={'success': False, 'error': 'Failed to delete keywords'})
    @log_execution()
    async def delete_keywords(self, rule_id: int, keywords: List[str]) -> Dict[str, Any]:
        """从规则中删除关键字 (原生异步)"""
        async with self.container.db.session() as session:
            # 获取规则信息
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            if not rule:
                return {'success': False, 'error': '规则不存在'}
            
            # 保存聊天ID用于清除缓存
            source_chat_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
            target_chat_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
            
            # 批量删除关键字
            
            delete_stmt = delete(Keyword).where(
                Keyword.rule_id == rule_id,
                Keyword.keyword.in_(keywords)
            )
            delete_result = await session.execute(delete_stmt)
            deleted_count = delete_result.rowcount
            await session.commit()
            
            result = {
                'success': True,
                'message': f'关键字删除成功，共删除 {deleted_count} 个关键字',
                'source_chat_id': source_chat_id,
                'target_chat_id': target_chat_id
            }
        
        # 清除相关缓存 (Unified)
        if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
            self.container.rule_repo.clear_cache(result['source_chat_id'])
            self.container.rule_repo.clear_cache(result['target_chat_id'])
        
        return result
    
    @handle_errors(default_return={'success': False, 'error': 'Failed to add replace rules'})
    @log_execution()
    async def add_replace_rules(self, rule_id: int, patterns: List[str], replacements: List[str], is_regex: bool = False) -> Dict[str, Any]:
        """添加替换规则到规则 (原生异步)"""
        async with self.container.db.session() as session:
            # 获取规则信息
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            if not rule:
                return {'success': False, 'error': '规则不存在'}
            
            # 保存聊天ID用于清除缓存
            source_chat_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
            target_chat_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
            
            # 批量添加替换规则
            
            # 1. 批量查询已存在的替换规则
            if patterns:
                existing_stmt = select(ReplaceRule.pattern).filter(
                    ReplaceRule.rule_id == rule_id,
                    ReplaceRule.pattern.in_(patterns),
                    ReplaceRule.is_regex == is_regex
                )
                existing_result = await session.execute(existing_stmt)
                existing_patterns = set(existing_result.scalars().all())
            else:
                existing_patterns = set()
            
            # 2. 筛选出真正需要新增的替换规则
            new_replace_rules = []
            for pattern, replacement in zip(patterns, replacements):
                if pattern not in existing_patterns:
                    new_replace_rules.append({
                        'pattern': pattern,
                        'replacement': replacement
                    })
            
            # 3. 批量添加新替换规则
            if new_replace_rules:
                new_replace_objects = [
                    ReplaceRule(
                        rule_id=rule_id,
                        pattern=r['pattern'],
                        content=r['replacement'],
                        is_regex=is_regex
                    ) for r in new_replace_rules
                ]
                session.add_all(new_replace_objects)
            
            await session.commit()
            result = {
                'success': True,
                'message': f'替换规则添加成功，新增 {len(new_replace_rules)} 个，跳过 {len(patterns) - len(new_replace_rules)} 个重复项',
                'source_chat_id': source_chat_id,
                'target_chat_id': target_chat_id
            }
        
        # 清除相关缓存 (Unified)
        if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
            self.container.rule_repo.clear_cache(result['source_chat_id'])
            self.container.rule_repo.clear_cache(result['target_chat_id'])
        
        return result
    
    @handle_errors(default_return={'success': False, 'error': 'Failed to delete replace rules'})
    @log_execution()
    async def delete_replace_rules(self, rule_id: int, patterns: List[str]) -> Dict[str, Any]:
        """从规则中删除替换规则 (原生异步)"""
        async with self.container.db.session() as session:
            # 获取规则信息
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat)
            ).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            if not rule:
                return {'success': False, 'error': '规则不存在'}
            
            # 保存聊天ID用于清除缓存
            source_chat_id = int(rule.source_chat.telegram_chat_id) if rule.source_chat else None
            target_chat_id = int(rule.target_chat.telegram_chat_id) if rule.target_chat else None
            
            # 批量删除替换规则
            
            delete_stmt = delete(ReplaceRule).where(
                ReplaceRule.rule_id == rule_id,
                ReplaceRule.pattern.in_(patterns)
            )
            delete_result = await session.execute(delete_stmt)
            deleted_count = delete_result.rowcount
            await session.commit()
            
            result = {
                'success': True,
                'message': f'替换规则删除成功，共删除 {deleted_count} 个替换规则',
                'source_chat_id': source_chat_id,
                'target_chat_id': target_chat_id
            }
        
        # 清除相关缓存 (Unified)
        if result.get('success') and result.get('source_chat_id') and result.get('target_chat_id'):
            self.container.rule_repo.clear_cache(result['source_chat_id'])
            self.container.rule_repo.clear_cache(result['target_chat_id'])
        
        return result

    @handle_errors(default_return={'success': False, 'error': 'Failed to add keywords to all rules'})
    async def add_keywords_all_rules(self, keywords: List[str], is_regex: bool = False, is_blacklist: bool = True) -> Dict[str, Any]:
        """批量添加关键字到所有规则"""
        async with self.container.db.session() as session:
            # 1. 获取所有规则 id
            stmt = select(ForwardRule.id)
            result = await session.execute(stmt)
            rule_ids = result.scalars().all()
            
            if not rule_ids:
                return {'success': True, 'message': '系统中暂无任何转发规则', 'added_count': 0}
            
            total_added = 0
            # 2. 遍历每个规则进行添加
            for r_id in rule_ids:
                # 检查重复
                existing_stmt = select(Keyword.keyword).filter(
                    Keyword.rule_id == r_id,
                    Keyword.keyword.in_(keywords),
                    Keyword.is_regex == is_regex,
                    Keyword.is_blacklist == is_blacklist
                )
                existing_result = await session.execute(existing_stmt)
                existing_set = set(existing_result.scalars().all())
                
                new_kws = [k for k in keywords if k not in existing_set]
                if new_kws:
                    new_objs = [Keyword(rule_id=r_id, keyword=k, is_regex=is_regex, is_blacklist=is_blacklist) for k in new_kws]
                    session.add_all(new_objs)
                    total_added += len(new_objs)
            
            await session.commit()
            
            # 3. 清理所有缓存 (Unified)
            self.container.rule_repo.clear_cache()
            
            return {
                'success': True, 
                'message': f'已同步添加 {total_added} 个关键字到 {len(rule_ids)} 条规则',
                'added_count': total_added,
                'rule_count': len(rule_ids)
            }

    @handle_errors(default_return={'success': False, 'error': 'Failed to delete keywords from all rules'})
    async def delete_keywords_all_rules(self, keywords: List[str]) -> Dict[str, Any]:
        """从所有规则中删除指定关键字"""
        async with self.container.db.session() as session:
            stmt = delete(Keyword).where(Keyword.keyword.in_(keywords))
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            await session.commit()
            
            # 3. 清理所有缓存 (Unified)
            self.container.rule_repo.clear_cache()
            
            return {
                'success': True,
                'message': f'已从所有规则中删除共计 {deleted_count} 个关键字',
                'deleted_count': deleted_count
            }

    @handle_errors(default_return={'success': False, 'error': 'Failed to clear keywords'})
    async def clear_keywords(self, rule_id: int, is_regex: Optional[bool] = None) -> Dict[str, Any]:
        """清空指定规则的关键字"""
        async with self.container.db.session() as session:
            stmt = delete(Keyword).where(Keyword.rule_id == rule_id)
            if is_regex is not None:
                stmt = stmt.where(Keyword.is_regex == is_regex)
            
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            await session.commit()
            
            # 清理缓存 (这里为了简单，清理相关聊天的缓存)
            # 获取规则关联的聊天ID
            r_stmt = select(ForwardRule).filter_by(id=rule_id)
            r_result = await session.execute(r_stmt)
            rule = r_result.scalar_one_or_none()
            if rule:
                # 获取关联的 Chat
                sc_stmt = select(Chat).filter_by(id=rule.source_chat_id)
                sc_res = await session.execute(sc_stmt)
                sc = sc_res.scalar_one_or_none()
                if sc:
                    self.container.rule_repo.clear_cache(int(sc.telegram_chat_id))
            
            return {
                'success': True,
                'message': f'已清空 {deleted_count} 个关键字',
                'deleted_count': deleted_count
            }

    @handle_errors(default_return={'success': False, 'error': 'Failed to add replace rules to all rules'})
    async def add_replace_rules_all_rules(self, patterns: List[str], replacements: List[str], is_regex: bool = False) -> Dict[str, Any]:
        """批量添加替换规则到所有规则"""
        async with self.container.db.session() as session:
            stmt = select(ForwardRule.id)
            result = await session.execute(stmt)
            rule_ids = result.scalars().all()
            
            if not rule_ids:
                return {'success': True, 'message': '没有可用的规则', 'added_count': 0}
            
            total_added = 0
            for r_id in rule_ids:
                # 检查重复
                if patterns:
                    existing_stmt = select(ReplaceRule.pattern).filter(
                        ReplaceRule.rule_id == r_id,
                        ReplaceRule.pattern.in_(patterns)
                    )
                    existing_result = await session.execute(existing_stmt)
                    existing_patterns = set(existing_result.scalars().all())
                else:
                    existing_patterns = set()
                
                for p, r in zip(patterns, replacements):
                    if p not in existing_patterns:
                        new_obj = ReplaceRule(rule_id=r_id, pattern=p, content=r, is_regex=is_regex)
                        session.add_all([new_obj])
                        total_added += 1
            
            await session.commit()
            RuleQueryService.invalidate_all_caches()
            
            return {
                'success': True,
                'message': f'已为 {len(rule_ids)} 条规则添加 {total_added} 条替换规则',
                'added_count': total_added
            }

    @handle_errors(default_return={'success': False, 'error': 'Failed to clear replace rules'})
    async def clear_replace_rules(self, rule_id: int) -> Dict[str, Any]:
        """清空规则的所有替换规则"""
        async with self.container.db.session() as session:
            stmt = delete(ReplaceRule).where(ReplaceRule.rule_id == rule_id)
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            await session.commit()
            
            # 清理缓存
            # 获取规则关联的聊天ID (同样可以使用上面 clear_keywords 的逻辑)
            r_stmt = select(ForwardRule).filter_by(id=rule_id)
            r_result = await session.execute(r_stmt)
            rule = r_result.scalar_one_or_none()
            if rule and rule.source_chat:
               self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))

            return {
                'success': True,
                'message': f'已清空 {deleted_count} 个替换规则',
                'deleted_count': deleted_count
            }

    @handle_errors(default_return={'success': False, 'error': 'Export failed'})
    async def export_rule_config(self, rule_id: int, format: str = 'json') -> Dict[str, Any]:
        """导出规则配置 (支持 JSON/YAML)"""
        rule_data = await self.get_rule_detail(rule_id)
        if not rule_data.get('success'):
            return rule_data

        # 获取更详细的配置，包括 list
        async with self.container.db.session() as session:
            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.keywords),
                selectinload(ForwardRule.replace_rules)
            ).filter_by(id=rule_id)
            result = await session.execute(stmt)
            rule = result.scalar_one_or_none()
            
            export_data = {
                "meta": {
                    "version": "1.0",
                    "exported_at": datetime.utcnow().isoformat(),
                    "format": format
                },
                "rule": {
                    "forward_mode": getattr(rule, 'forward_mode', None),
                    "keywords": [
                        {"k": k.keyword, "rx": k.is_regex, "bl": k.is_blacklist} 
                        for k in rule.keywords
                    ],
                    "replace_rules": [
                        {"p": r.pattern, "c": r.content, "rx": r.is_regex}
                        for r in rule.replace_rules
                    ]
                }
            }
            
            if format.lower() == 'yaml':
                if not yaml:
                    return {'success': False, 'error': 'Server missing PyYAML library'}
                content = yaml.dump(export_data, allow_unicode=True, sort_keys=False)
                mime = 'application/x-yaml'
                ext = 'yaml'
            else:
                content = json.dumps(export_data, indent=2, ensure_ascii=False)
                mime = 'application/json'
                ext = 'json'
                
            return {
                'success': True,
                'content': content,
                'filename': f"rule_{rule_id}_export.{ext}",
                'mime_type': mime
            }

    @handle_errors(default_return={'success': False, 'error': 'Import failed'})
    async def import_rule_config(self, rule_id: int, content: str, format: str = 'json') -> Dict[str, Any]:
        """导入规则配置 (支持 JSON/YAML)"""
        try:
            if format.lower() == 'yaml' or (content.strip().startswith('meta:') or 'rule:' in content):
                if not yaml:
                     # 尝试简单的 json fallback? 不，这是 yaml
                     return {'success': False, 'error': 'Server missing PyYAML library'}
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
            
            if not isinstance(data, dict) or 'rule' not in data:
                 return {'success': False, 'error': 'Invalid format structure'}
            
            rule_payload = data['rule']
            
            # Application Logic
            # 1. Update Mode
            if 'forward_mode' in rule_payload and rule_payload['forward_mode']:
                await self.update_rule(rule_id, forward_mode=rule_payload['forward_mode'])
            
            stats = {"keywords": 0, "replace": 0}
            
            # 2. Keywords
            if 'keywords' in rule_payload:
                kw_list = rule_payload['keywords']
                # Group by types to use batch add
                # Actually our batch add is simple list of strings, so we loop or refactor
                # For simplicity, loop insert (Optimization: could bulk insert)
                # But let's use the existing bulk logic if possible, but that one is simple string list
                # So we do direct DB insert for custom objects
                async with self.container.db.session() as session:
                    for k in kw_list:
                        stmt = select(Keyword).filter_by(
                            rule_id=rule_id,
                            keyword=k['k'],
                            is_regex=k.get('rx', False),
                            is_blacklist=k.get('bl', True)
                        )
                        exists = (await session.execute(stmt)).first()
                        if not exists:
                            session.add(Keyword(
                                rule_id=rule_id, keyword=k['k'], 
                                is_regex=k.get('rx', False), is_blacklist=k.get('bl', True)
                            ))
                            stats['keywords'] += 1
                        
                    # 3. Replace Rules
                    if 'replace_rules' in rule_payload:
                        for r in rule_payload['replace_rules']:
                            stmt = select(ReplaceRule).filter_by(
                                rule_id=rule_id,
                                pattern=r['p'],
                                content=r['c']
                            )
                            exists = (await session.execute(stmt)).first()
                            if not exists:
                                session.add(ReplaceRule(
                                    rule_id=rule_id, pattern=r['p'], content=r['c'], is_regex=r.get('rx', False)
                                ))
                                stats['replace'] += 1
                    
                    await session.commit()
            
            # Invalidate Cache
            r_data = await self.get_rule_detail(rule_id)
            if r_data['success']:
                chat_title = r_data.get('source_chat', 'Unknown')
                # This is tricky without ID, but update_rule should have handled caches.
                # Actually import manually touched DB, so we must invalidate manually
                # Or re-fetch rule to get source_chat_id
                async with self.container.db.session() as session:
                    rr = await session.get(ForwardRule, rule_id)
                    if rr and rr.source_chat:
                        self.container.rule_repo.clear_cache(int(rr.source_chat.telegram_chat_id))

            return {
                'success': True,
                'message': f"Imported successfully. Added {stats['keywords']} keywords, {stats['replace']} replacement rules."
            }
            
        except Exception as e:
            return {'success': False, 'error': f"Parse error: {str(e)}"}
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            await session.commit()
            # 3. 清理所有缓存 (Unified)
            self.container.rule_repo.clear_cache()
            
            return {
                'success': True,
                'message': f'已清空 {deleted_count} 条替换规则',
                'deleted_count': deleted_count
            }
    
    @handle_errors(default_return={'success': False, 'error': 'Failed to get rule statistics'})
    @log_execution()
    async def get_rule_statistics(self) -> Dict[str, Any]:
        """获取规则统计信息 (原生异步)"""
        from utils.network.api_optimization import get_api_optimizer
        
        api_optimizer = get_api_optimizer()
        if api_optimizer:
            try:
                cached_stats = getattr(api_optimizer, '_rule_stats_cache', None)
                if cached_stats and self._is_cache_valid(cached_stats):
                    logger.info("使用缓存的规则统计数据")
                    return {'success': True, 'statistics': cached_stats['data'], 'cache_hit': True}
            except Exception:
                pass
        
        async with self.container.db.session() as session:
            total_rules = (await session.execute(select(func.count(ForwardRule.id)))).scalar() or 0
            enabled_rules = (await session.execute(select(func.count(ForwardRule.id)).filter_by(enable_rule=True))).scalar() or 0
            dedup_enabled_rules = (await session.execute(select(func.count(ForwardRule.id)).filter_by(enable_dedup=True))).scalar() or 0
            
            stats_data = {
                'total_rules': total_rules,
                'enabled_rules': enabled_rules,
                'disabled_rules': total_rules - enabled_rules,
                'dedup_enabled_rules': dedup_enabled_rules,
                'enabled_percentage': (enabled_rules / total_rules * 100) if total_rules > 0 else 0
            }
        
        if api_optimizer:
            import time
            api_optimizer._rule_stats_cache = {'data': stats_data, 'timestamp': time.time(), 'ttl': 300}
        
        return {'success': True, 'statistics': stats_data, 'cache_hit': False}
    
    def _is_cache_valid(self, cache_data: dict) -> bool:
        """检查缓存是否有效"""
        try:
            import time
            if not cache_data or 'timestamp' not in cache_data:
                return False
            
            ttl = cache_data.get('ttl', 300)  # 默认5分钟
            return (time.time() - cache_data['timestamp']) < ttl
        except Exception:
            return False
    
    # [新增] 统一的绑定逻辑
    async def bind_chat(self, user_client, source_input: str, target_input: str = None, current_chat_id: int = None) -> Dict[str, Any]:
        """
        处理绑定逻辑：解析实体 -> 获取/创建 Chat -> 创建规则 -> 清理缓存
        替代 command_handlers.py 中的 handle_bind_command 核心逻辑
        """
        async with self.container.db.session() as session:
            try:
                # 1. 解析源实体
                source_entity = await self._resolve_entity(user_client, source_input)
                if not source_entity:
                    return {'success': False, 'error': f'无法解析源聊天: {source_input}'}

                # 2. 解析目标实体 (如果没传，默认当前聊天)
                if target_input:
                    target_entity = await self._resolve_entity(user_client, target_input)
                elif current_chat_id:
                    target_entity = await user_client.get_entity(current_chat_id)
                else:
                    return {'success': False, 'error': '未指定目标聊天'}

                if not target_entity:
                    return {'success': False, 'error': f'无法解析目标聊天: {target_input}'}

                # 3. 数据库操作 (Get Or Create Chat)
                source_chat_db = await self._get_or_create_chat(session, source_entity)
                target_chat_db = await self._get_or_create_chat(session, target_entity)

                # 4. 设置 current_add_id (上下文)
                target_chat_db.current_add_id = source_chat_db.telegram_chat_id
                session.add(target_chat_db)

                # 5. 创建或获取规则
                stmt = select(ForwardRule).filter_by(
                    source_chat_id=source_chat_db.id,
                    target_chat_id=target_chat_db.id
                )
                existing_rule = (await session.execute(stmt)).scalar_one_or_none()

                if existing_rule:
                    return {
                        'success': True, 
                        'message': '规则已存在', 
                        'rule_id': existing_rule.id,
                        'is_new': False,
                        'source_name': source_chat_db.name,
                        'target_name': target_chat_db.name
                    }

                new_rule = ForwardRule(
                    source_chat_id=source_chat_db.id,
                    target_chat_id=target_chat_db.id
                )
                
                # 自转发特殊处理
                if source_chat_db.id == target_chat_db.id:
                    new_rule.forward_mode = ForwardMode.WHITELIST
                    new_rule.add_mode = AddMode.WHITELIST

                session.add(new_rule)
                await session.commit()
                await session.refresh(new_rule)

                # 6. 关键：缓存失效
                self.container.rule_repo.clear_cache(int(source_chat_db.telegram_chat_id))

                return {
                    'success': True,
                    'message': '规则创建成功',
                    'rule_id': new_rule.id,
                    'is_new': True,
                    'source_name': source_chat_db.name,
                    'target_name': target_chat_db.name
                }

            except Exception as e:
                await session.rollback()
                logger.error(f"Bind chat failed: {e}", exc_info=True)
                return {'success': False, 'error': str(e)}

    # [新增] 辅助方法：解析实体
    async def _resolve_entity(self, client, input_str: str):
        try:
            # 优先使用优化器
            from utils.network.api_optimization import get_api_optimizer
            optimizer = get_api_optimizer()
            if optimizer:
                # 这里假设优化器有解析单体的方法，如果没有，降级使用 client
                # 简单处理：如果是链接，尝试解析；如果是 ID，直接转换
                pass
            
            # Telethon 原生解析 (最稳健)
            return await client.get_entity(input_str)
        except Exception as e:
            logger.warning(f"Entity resolution failed for {input_str}: {e}")
            return None

    # [新增] 辅助方法：获取或创建 Chat
    async def _get_or_create_chat(self, session, entity):
        chat_id = str(entity.id)
        # 处理频道ID可能的 -100 前缀差异 (Telethon entity.id 通常不带 -100，但存储时我们通常带)
        # 这里建议统一逻辑，假设 Entity ID 是纯数字，存储时根据类型判断
        # 为简化，暂且直接存 str(id)
        
        stmt = select(Chat).filter_by(telegram_chat_id=chat_id)
        chat = (await session.execute(stmt)).scalar_one_or_none()
        
        if not chat:
            title = getattr(entity, 'title', None) or \
                    f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip() or \
                    "Unknown"
            chat = Chat(telegram_chat_id=chat_id, name=title)
            session.add(chat)
            await session.flush()
        return chat

    @handle_errors(default_return={'success': False, 'error': 'Failed to export keywords'})
    async def export_keywords(self, rule_id: int) -> List[str]:
        """导出规则的关键字为行列表"""
        async with self.container.db.session() as session:
            stmt = select(Keyword).filter_by(rule_id=rule_id)
            result = await session.execute(stmt)
            keywords = result.scalars().all()
            
            lines = []
            for k in keywords:
                # 兼容原有格式: "keyword" 0/1 (1=blacklist, 0=whitelist)
                line = f"{k.keyword} {1 if k.is_blacklist else 0}"
                lines.append(line)
            return lines

    @handle_errors(default_return={'success': False, 'error': 'Failed to export replace rules'})
    async def export_replace_rules(self, rule_id: int) -> List[str]:
        """导出规则的替换规则为行列表"""
        async with self.container.db.session() as session:
            stmt = select(ReplaceRule).filter_by(rule_id=rule_id)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            
            lines = []
            for r in rules:
                line = f"{r.pattern}\t{r.content if r.content else ''}"
                lines.append(line)
            return lines

    @handle_errors(default_return={'success': False, 'error': 'Failed to import keywords'})
    async def import_keywords(self, rule_id: int, lines: List[str], is_regex: bool = False) -> Dict[str, Any]:
        """从行列表导入关键字"""
        async with self.container.db.session() as session:
            # 获取现有关键字用于去重
            stmt = select(Keyword.keyword).filter_by(rule_id=rule_id, is_regex=is_regex)
            existing_kws = set((await session.execute(stmt)).scalars().all())
            
            new_objs = []
            duplicate_count = 0
            for line in lines:
                parts = line.rsplit(None, 1)
                if len(parts) < 2: continue
                
                keyword = parts[0]
                flag = parts[1]
                if flag not in ('0', '1'): continue
                
                is_blk = flag == '1'
                if keyword in existing_kws:
                    duplicate_count += 1
                    continue
                
                new_objs.append(Keyword(rule_id=rule_id, keyword=keyword, is_regex=is_regex, is_blacklist=is_blk))
                existing_kws.add(keyword)
            
            if new_objs:
                session.add_all(new_objs)
                await session.commit()
                self.container.rule_repo.clear_cache()
                
            return {
                'success': True,
                'imported_count': len(new_objs),
                'duplicate_count': duplicate_count
            }

    @handle_errors(default_return={'success': False, 'error': 'Failed to import replace rules'})
    async def import_replace_rules(self, rule_id: int, lines: List[str]) -> Dict[str, Any]:
        """从行列表导入替换规则"""
        async with self.container.db.session() as session:
            stmt = select(ReplaceRule.pattern, ReplaceRule.content).filter_by(rule_id=rule_id)
            existing = set((await session.execute(stmt)).all())
            
            new_objs = []
            for line in lines:
                parts = line.split('\t', 1)
                if not parts: continue
                pat = parts[0].strip()
                cont = parts[1].strip() if len(parts) > 1 else ""
                
                if (pat, cont) not in existing:
                    new_objs.append(ReplaceRule(rule_id=rule_id, pattern=pat, content=cont))
                    existing.add((pat, cont))
            
            if new_objs:
                session.add_all(new_objs)
                # 开启替换模式
                stmt_rule = select(ForwardRule).filter_by(id=rule_id)
                rule = (await session.execute(stmt_rule)).scalar_one_or_none()
                if rule:
                    rule.is_replace = True
                    session.add(rule)
                
                await session.commit()
                self.container.rule_repo.clear_cache()
                
            return {
                'success': True,
                'imported_count': len(new_objs)
            }

    @handle_errors(default_return={'success': False, 'error': 'Failed to import excel data'})
    async def import_excel(self, keywords_rows: List[Dict], replacement_rows: List[Dict]) -> Dict[str, Any]:
        """批量导入 Excel 数据"""
        async with self.container.db.session() as session:
            kw_success = 0
            kw_failed = 0
            r_success = 0
            r_failed = 0
            
            # 1. 处理关键字
            if keywords_rows:
                rule_ids = {int(r['rule_id']) for r in keywords_rows if r.get('rule_id')}
                stmt_rules = select(ForwardRule.id).where(ForwardRule.id.in_(rule_ids))
                valid_rule_ids = set((await session.execute(stmt_rules)).scalars().all())
                
                stmt_existing = select(Keyword.rule_id, Keyword.keyword, Keyword.is_regex, Keyword.is_blacklist).where(Keyword.rule_id.in_(valid_rule_ids))
                existing_kws = set((await session.execute(stmt_existing)).all())
                
                new_keywords = []
                for row in keywords_rows:
                    try:
                        rid = int(row.get('rule_id'))
                        if rid not in valid_rule_ids:
                            kw_failed += 1; continue
                        kw_text = (row.get('keyword') or '').strip()
                        if not kw_text:
                            kw_failed += 1; continue
                        is_reg = bool(row.get('is_regex'))
                        is_blk = bool(row.get('is_blacklist'))
                        
                        if (rid, kw_text, is_reg, is_blk) not in existing_kws:
                            new_keywords.append(Keyword(rule_id=rid, keyword=kw_text, is_regex=is_reg, is_blacklist=is_blk))
                            existing_kws.add((rid, kw_text, is_reg, is_blk))
                            kw_success += 1
                        else:
                            kw_failed += 1
                    except: kw_failed += 1
                if new_keywords: session.add_all(new_keywords)

            # 2. 处理替换规则
            if replacement_rows:
                rule_ids = {int(r['rule_id']) for r in replacement_rows if r.get('rule_id')}
                stmt_rules = select(ForwardRule.id).where(ForwardRule.id.in_(rule_ids))
                valid_rule_ids_r = set((await session.execute(stmt_rules)).scalars().all())
                
                stmt_existing_r = select(ReplaceRule.rule_id, ReplaceRule.pattern, ReplaceRule.content).where(ReplaceRule.rule_id.in_(valid_rule_ids_r))
                existing_replaces = {(res.rule_id, res.pattern, res.content or "") for res in (await session.execute(stmt_existing_r)).all()}
                
                new_replaces = []
                rules_to_enable = set()
                for row in replacement_rows:
                    try:
                        rid = int(row.get('rule_id'))
                        if rid not in valid_rule_ids_r:
                            r_failed += 1; continue
                        pat = (row.get('pattern') or '').strip()
                        if not pat:
                            r_failed += 1; continue
                        cont = row.get('content') or ""
                        
                        if (rid, pat, cont) not in existing_replaces:
                            new_replaces.append(ReplaceRule(rule_id=rid, pattern=pat, content=cont))
                            existing_replaces.add((rid, pat, cont))
                            r_success += 1
                            rules_to_enable.add(rid)
                        else:
                            r_failed += 1
                    except: r_failed += 1
                if new_replaces: session.add_all(new_replaces)
                
                if rules_to_enable:
                    stmt_update = select(ForwardRule).where(ForwardRule.id.in_(rules_to_enable), ForwardRule.is_replace == False)
                    for rule in (await session.execute(stmt_update)).scalars().all():
                        rule.is_replace = True

            await session.commit()
            self.container.rule_repo.clear_cache()
            
            return {
                'success': True,
                'kw_success': kw_success,
                'kw_failed': kw_failed,
                'r_success': r_success,
                'r_failed': r_failed
            }

    # [新增] 清空所有数据
    async def clear_all_data(self) -> Dict[str, Any]:
        """危险操作：清空所有业务数据"""
        async with self.container.db.session() as session:
            try:
                # 级联删除顺序：Keyword/Replace -> Rule -> Chat
                await session.execute(delete(Keyword))
                await session.execute(delete(ReplaceRule)) 
                await session.execute(delete(ForwardRule))
                await session.execute(delete(Chat))
                # 还可以清理 MediaSignature, TaskQueue 等
                
                await session.commit()
                
                # 也可以在这里调用 Redis flush
                return {'success': True, 'message': '所有数据已清空'}
            except Exception as e:
                await session.rollback()
                return {'success': False, 'error': str(e)}

# 全局服务实例
rule_management_service = RuleManagementService()
