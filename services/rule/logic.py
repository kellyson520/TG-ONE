"""
Rule Management Logic Service
Handles complex logic like Copying Rules, Keywords Management, and Imports/Exports.
"""
from typing import Dict, Any, List, Optional
import logging
import json
from datetime import datetime

from core.helpers.error_handler import handle_errors
from enums.enums import ForwardMode
from schemas.sub_rules import KeywordDTO, ReplaceRuleDTO

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


class RuleLogicService:
    @property
    def container(self):
        from core.container import container
        return container
        
    @handle_errors(default_return={'success': False, 'error': 'Rule copy failed'})
    async def copy_rule(self, source_rule_id: int, target_rule_id: Optional[int] = None) -> Dict[str, Any]:
        """增强版规则复制逻辑"""
        if not target_rule_id:
             return {'success': False, 'error': 'Target Rule ID required'}
             
        # Use Repository to get ORM for deep modification
        source_rule = await self.container.rule_repo.get_full_rule_orm(source_rule_id)
        if not source_rule:
            return {'success': False, 'error': f'Source rule {source_rule_id} not found'}
            
        target_rule = await self.container.rule_repo.get_full_rule_orm(target_rule_id)
        if not target_rule:
            return {'success': False, 'error': f'Target rule {target_rule_id} not found'}

        # 1. Copy settings (Base attributes)
        exclude_cols = {'id', 'source_chat_id', 'target_chat_id', 'created_at', 'updated_at'}
        for column in source_rule.__table__.columns:
            if column.name not in exclude_cols:
                setattr(target_rule, column.name, getattr(source_rule, column.name))

        # 2. Copy associations
        # Keywords
        target_rule.keywords.clear()
        from models.models import Keyword, ReplaceRule, MediaExtensions, MediaTypes, RuleSync
        for kw in source_rule.keywords:
            target_rule.keywords.append(Keyword(
                keyword=kw.keyword, is_regex=kw.is_regex, is_blacklist=kw.is_blacklist
            ))
            
        # Replace Rules
        target_rule.replace_rules.clear()
        for rr in source_rule.replace_rules:
            target_rule.replace_rules.append(ReplaceRule(
                pattern=rr.pattern, content=rr.content
            ))
            
        # Media Extensions
        target_rule.media_extensions.clear()
        for ext in source_rule.media_extensions:
            target_rule.media_extensions.append(MediaExtensions(extension=ext.extension))
            
        # Media Types
        if source_rule.media_types:
            if not target_rule.media_types:
                target_rule.media_types = MediaTypes()
            
            from sqlalchemy import inspect
            media_inspector = inspect(MediaTypes)
            for column in media_inspector.columns:
                if column.key not in ["id", "rule_id"]:
                     setattr(target_rule.media_types, column.key, getattr(source_rule.media_types, column.key))
                     
        # Rule Syncs
        target_rule.rule_syncs.clear()
        for sync in source_rule.rule_syncs:
            if sync.sync_rule_id != target_rule.id:
                target_rule.rule_syncs.append(RuleSync(sync_rule_id=sync.sync_rule_id))
            
        source_chat_id = int(target_rule.source_chat.telegram_chat_id) if target_rule.source_chat else None
        await self.container.rule_repo.save_rule(target_rule)
        
        if source_chat_id:
            self.container.rule_repo.clear_cache(source_chat_id)
        
        return {'success': True, 'message': 'Rule copied successfully'}

    @handle_errors(default_return={'success': False, 'error': 'Chat binding failed'})
    async def bind_chat(self, client, source_input: str, target_input: Optional[str] = None, current_chat_id: Optional[int] = None) -> Dict[str, Any]:
        """一键绑定两个聊天"""
        from core.helpers.id_utils import get_or_create_chat_async
        
        # 1. 寻找或创建目标聊天
        target_name, target_tid, target_chat_obj = await get_or_create_chat_async(client, target_input)
        if not target_chat_obj:
             return {'success': False, 'error': f'无法识别目标聊天: {target_input}'}
             
        # 2. 寻找或创建源聊天
        source_chat_name, source_chat_id, source_chat_obj = await get_or_create_chat_async(client, source_input)
        if not source_chat_id:
             return {'success': False, 'error': f'无法获取源聊天信息: {source_input}'}
             
        # 3. 检查规则是否存在
        existing_rule = await self.container.rule_repo.get_rule_by_source_target(source_chat_obj.id, target_chat_obj.id)
        
        is_new = False
        if not existing_rule:
            new_rule = await self.container.rule_repo.create_rule(
                source_chat_id=source_chat_obj.id,
                target_chat_id=target_chat_obj.id,
                enable_rule=True,
                forward_mode=ForwardMode.BLACKLIST,
                created_at=datetime.utcnow()
            )
            is_new = True
            rule_id = new_rule.id
        else:
            rule_id = existing_rule.id
        
        # Clear Cache
        self.container.rule_repo.clear_cache(int(source_chat_id))
        
        return {
            'success': True,
            'is_new': is_new,
            'rule_id': rule_id,
            'source_name': source_chat_name,
            'target_name': target_name
        }

    @handle_errors(default_return={'success': False, 'error': 'Adding keywords failed'})
    async def add_keywords(self, rule_id: int, keywords: List[str], is_regex: bool = False, is_blacklist: bool = False) -> Dict[str, Any]:
        """批量添加关键字"""
        from models.models import Keyword
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
            
        existing_kws = {kw.keyword for kw in rule.keywords if kw.is_blacklist == is_blacklist}
        added_count = 0
        for kw_text in keywords:
            if kw_text not in existing_kws:
                rule.keywords.append(Keyword(
                    keyword=kw_text,
                    is_regex=is_regex,
                    is_blacklist=is_blacklist
                ))
                added_count += 1
        
        if added_count > 0:
            await self.container.rule_repo.save_rule(rule)
            self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
            
        return {'success': True, 'added': added_count}

    @handle_errors(default_return={'success': False, 'error': 'Copying keywords failed'})
    async def copy_keywords_from_rule(self, source_rule_id: int, target_rule_id: int, is_regex: Optional[bool] = None) -> Dict[str, Any]:
        """从源规则复制关键字到目标规则"""
        from models.models import Keyword
        source_rule = await self.container.rule_repo.get_full_rule_orm(source_rule_id)
        target_rule = await self.container.rule_repo.get_full_rule_orm(target_rule_id)
        
        if not source_rule or not target_rule:
            return {'success': False, 'error': 'Source or Target rule not found'}
            
        existing_kws = {(kw.keyword, kw.is_regex, kw.is_blacklist) for kw in target_rule.keywords}
        added_count = 0
        skip_count = 0
        
        for kw in source_rule.keywords:
            if is_regex is not None and kw.is_regex != is_regex:
                continue
                
            key = (kw.keyword, kw.is_regex, kw.is_blacklist)
            if key not in existing_kws:
                target_rule.keywords.append(Keyword(
                    keyword=kw.keyword,
                    is_regex=kw.is_regex,
                    is_blacklist=kw.is_blacklist
                ))
                added_count += 1
                existing_kws.add(key)
            else:
                skip_count += 1
                
        if added_count > 0:
            await self.container.rule_repo.save_rule(target_rule)
            self.container.rule_repo.clear_cache(int(target_rule.source_chat.telegram_chat_id))
            
        return {'success': True, 'added': added_count, 'skipped': skip_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting keywords failed'})
    async def delete_keywords(self, rule_id: int, keywords: List[str]) -> Dict[str, Any]:
        """批量删除关键字"""
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
            
        initial_count = len(rule.keywords)
        rule.keywords = [kw for kw in rule.keywords if kw.keyword not in keywords]
        deleted_count = initial_count - len(rule.keywords)
        
        if deleted_count > 0:
            await self.container.rule_repo.save_rule(rule)
            self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
            
        return {'success': True, 'deleted': deleted_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting keywords by index failed'})
    async def delete_keywords_by_indices(self, rule_id: int, indices: List[int]) -> Dict[str, Any]:
        """通过 1-indexed 序号批量删除关键字"""
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
            
        initial_count = len(rule.keywords)
        valid_indices = sorted(set(i for i in indices if 1 <= i <= initial_count), reverse=True)
        
        if not valid_indices:
            return {'success': True, 'deleted': 0}
            
        for idx in valid_indices:
            del rule.keywords[idx - 1]
            
        await self.container.rule_repo.save_rule(rule)
        self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
        
        return {'success': True, 'deleted': len(valid_indices)}

    @handle_errors(default_return={'success': False, 'error': 'Clearing keywords failed'})
    async def clear_keywords(self, rule_id: int) -> Dict[str, Any]:
        """清空规则的所有关键字"""
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
        
        initial_count = len(rule.keywords)
        if initial_count == 0:
             return {'success': True, 'deleted': 0}
        
        rule.keywords.clear()
        
        await self.container.rule_repo.save_rule(rule)
        self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
        
        return {'success': True, 'deleted': initial_count}

    async def get_keywords(self, rule_id: int, is_blacklist: Optional[bool] = True) -> List[KeywordDTO]:
        """获取关键字列表"""
        rule_dto = await self.container.rule_repo.get_by_id(rule_id)
        if not rule_dto: return []
        if is_blacklist is None:
            return rule_dto.keywords
        return [kw for kw in rule_dto.keywords if kw.is_blacklist == is_blacklist]

    async def get_replace_rules(self, rule_id: int) -> List[ReplaceRuleDTO]:
        """获取替换规则列表"""
        rule_dto = await self.container.rule_repo.get_by_id(rule_id)
        if not rule_dto: return []
        return rule_dto.replace_rules

    @handle_errors(default_return={'success': False, 'error': 'Clear all data failed'})
    async def clear_all_data(self) -> Dict[str, Any]:
        """清空所有规则 data (危险操作)"""
        count = await self.container.rule_repo.delete_all_rules()
        self.container.rule_repo.clear_cache()
        return {'success': True, 'message': f'所有规则数据已清空 (影响 {count} 条)'}
        
    async def get_rule_statistics(self) -> Dict[str, Any]:
        """获取规则统计信息"""
        count = await self.container.rule_repo.get_rule_count()
        return {'total_rules': count}

    async def cleanup_orphan_chats(self, rule_deleted=None) -> int:
        """检查并清理不再与任何规则关联的聊天记录"""
        
        chat_ids_to_check = []
        if rule_deleted:
            if hasattr(rule_deleted, 'source_chat_id') and rule_deleted.source_chat_id:
                chat_ids_to_check.append(rule_deleted.source_chat_id)
            if hasattr(rule_deleted, 'target_chat_id') and rule_deleted.target_chat_id:
                chat_ids_to_check.append(rule_deleted.target_chat_id)
        else:
            chat_ids_to_check = await self.container.rule_repo.get_all_chat_ids()

        orphan_ids = []
        for chat_id in chat_ids_to_check:
            refs = await self.container.rule_repo.count_rule_refs_for_chat(chat_id)
            if refs['as_source'] == 0 and refs['as_target'] == 0:
                chat_dto = await self.container.rule_repo.find_chat_by_id_internal(chat_id)
                if chat_dto:
                    affected_chats = await self.container.rule_repo.get_chats_using_add_id(chat_dto.telegram_chat_id)
                    for other in affected_chats:
                        await self.container.rule_repo.update_chat_current_add_id(other.id, None)
                    orphan_ids.append(chat_id)
        
        if orphan_ids:
            return await self.container.rule_repo.delete_orphan_chats(orphan_ids)
        return 0

    @handle_errors(default_return={'success': False, 'error': 'Adding replace rules failed'})
    async def add_replace_rules(self, rule_id: int, patterns: List[str], replacements: List[str], is_regex: bool = False) -> Dict[str, Any]:
        """批量添加替换规则"""
        from models.models import ReplaceRule
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
            
        existing_patterns = {rr.pattern for rr in rule.replace_rules}
        added_count = 0
        for i, pattern in enumerate(patterns):
            replacement = replacements[i] if i < len(replacements) else ""
            if pattern not in existing_patterns:
                rule.replace_rules.append(ReplaceRule(
                    pattern=pattern,
                    content=replacement
                ))
                added_count += 1
        
        if added_count > 0:
            await self.container.rule_repo.save_rule(rule)
            self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
            
        return {'success': True, 'added': added_count}

    @handle_errors(default_return={'success': False, 'error': 'Copying replace rules failed'})
    async def copy_replace_rules_from_rule(self, source_rule_id: int, target_rule_id: int) -> Dict[str, Any]:
        """从源规则复制替换规则到目标规则"""
        from models.models import ReplaceRule
        source_rule = await self.container.rule_repo.get_full_rule_orm(source_rule_id)
        target_rule = await self.container.rule_repo.get_full_rule_orm(target_rule_id)
        
        if not source_rule or not target_rule:
            return {'success': False, 'error': 'Source or Target rule not found'}
            
        existing_replaces = {(r.pattern, r.content) for r in target_rule.replace_rules}
        added_count = 0
        skip_count = 0
        
        for rr in source_rule.replace_rules:
            key = (rr.pattern, rr.content)
            if key not in existing_replaces:
                target_rule.replace_rules.append(ReplaceRule(
                    pattern=rr.pattern,
                    content=rr.content
                ))
                added_count += 1
                existing_replaces.add(key)
            else:
                skip_count += 1
                
        if added_count > 0:
            await self.container.rule_repo.save_rule(target_rule)
            self.container.rule_repo.clear_cache(int(target_rule.source_chat.telegram_chat_id))
            
        return {'success': True, 'added': added_count, 'skipped': skip_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting replace rules failed'})
    async def delete_replace_rules(self, rule_id: int, patterns: List[str]) -> Dict[str, Any]:
        """批量删除替换规则"""
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
            
        initial_count = len(rule.replace_rules)
        rule.replace_rules = [rr for rr in rule.replace_rules if rr.pattern not in patterns]
        deleted_count = initial_count - len(rule.replace_rules)
        
        if deleted_count > 0:
            await self.container.rule_repo.save_rule(rule)
            self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
            
        return {'success': True, 'deleted': deleted_count}

    @handle_errors(default_return={'success': False, 'error': 'Deleting replace rules by index failed'})
    async def delete_replace_rules_by_indices(self, rule_id: int, indices: List[int]) -> Dict[str, Any]:
        """通过 1-indexed 序号批量删除替换规则"""
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
            
        initial_count = len(rule.replace_rules)
        # 转换为集合并过滤非法索引
        valid_indices = sorted(set(i for i in indices if 1 <= i <= initial_count), reverse=True)
        
        if not valid_indices:
            return {'success': True, 'deleted': 0}
            
        for idx in valid_indices:
            # SQLAlchemy will handle the deletion from list
            del rule.replace_rules[idx - 1]
            
        await self.container.rule_repo.save_rule(rule)
        self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
        
        return {'success': True, 'deleted': len(valid_indices)}

    @handle_errors(default_return={'success': False, 'error': 'Adding push config failed'})
    async def add_push_config(self, rule_id: int, push_channel: str) -> Dict[str, Any]:
        """为规则添加推送频道并处理同步"""
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule:
                return {'success': False, 'error': 'Rule not found'}
                
            # 检查是否已存在
            stmt = select(PushConfig).filter_by(rule_id=rule.id, push_channel=push_channel)
            existing = (await s.execute(stmt)).scalar_one_or_none()
            if existing:
                 return {'success': True, 'message': 'Push channel already exists'}
            
            # 创建新配置
            is_email = push_channel.startswith(("mailto://", "mailtos://", "email://"))
            config = PushConfig(
                rule_id=rule.id,
                push_channel=push_channel,
                enable_push_channel=True,
                media_send_mode="Multiple" if is_email else "Single"
            )
            s.add(config)
            rule.enable_push = True
            
            # 同步
            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                sync_results = await s.execute(sync_stmt)
                for sync_obj in sync_results.scalars().all():
                     target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                     if target:
                         # 检查目标规则是否已有同名频道
                         t_stmt = select(PushConfig).filter_by(rule_id=target.id, push_channel=push_channel)
                         t_existing = (await s.execute(t_stmt)).scalar_one_or_none()
                         if not t_existing:
                             s.add(PushConfig(
                                 rule_id=target.id,
                                 push_channel=push_channel,
                                 enable_push_channel=True,
                                 media_send_mode=config.media_send_mode
                             ))
                             target.enable_push = True
            
            await s.commit()
            if rule.source_chat:
                self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
                
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Clearing replace rules failed'})
    async def clear_replace_rules(self, rule_id: int) -> Dict[str, Any]:
        """清空规则的所有替换规则"""
        rule = await self.container.rule_repo.get_full_rule_orm(rule_id)
        if not rule:
            return {'success': False, 'error': 'Rule not found'}
        
        initial_count = len(rule.replace_rules)
        if initial_count == 0:
             return {'success': True, 'deleted': 0}

        rule.replace_rules.clear()
        
        await self.container.rule_repo.save_rule(rule)
        self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
        
        return {'success': True, 'deleted': initial_count}

    @handle_errors(default_return={'success': False, 'error': 'Export failed'})
    async def export_rule_config(self, rule_id: int, format: str = "json") -> Dict[str, Any]:
        """导出规则配置"""
        rule_dto = await self.container.rule_repo.get_by_id(rule_id)
        if not rule_dto:
            return {'success': False, 'error': 'Rule not found'}
            
        # Transform to export dict
        export_data = {
            "rule": {
                "forward_mode": rule_dto.forward_mode.value if hasattr(rule_dto.forward_mode, 'value') else rule_dto.forward_mode,
                "use_bot": rule_dto.use_bot,
                "message_mode": rule_dto.message_mode.value if hasattr(rule_dto.message_mode, 'value') else rule_dto.message_mode,
                "is_replace": rule_dto.is_replace,
                "keywords": [{"k": kw.keyword, "rx": kw.is_regex, "bl": kw.is_blacklist} for kw in rule_dto.keywords],
                "replace_rules": [{"p": rr.pattern, "c": rr.content, "rx": False} for rr in rule_dto.replace_rules]
            }
        }
        
        if format.lower() == "yaml":
            if not yaml: return {'success': False, 'error': 'PyYAML not installed'}
            content = yaml.dump(export_data, allow_unicode=True)
        else:
            content = json.dumps(export_data, ensure_ascii=False, indent=2)
            
        return {'success': True, 'content': content}

    @handle_errors(default_return={'success': False, 'error': 'Import failed'})
    async def import_rule_config(self, rule_id: int, content: str, format: str = "json") -> Dict[str, Any]:
        """导入规则配置"""
        if format.lower() == "yaml":
            if not yaml: return {'success': False, 'error': 'PyYAML not installed'}
            data = yaml.safe_load(content)
        else:
            import json
            data = json.loads(content)
            
        rule_data = data.get("rule", {})
        
        # 批量应用
        if "keywords" in rule_data:
            for kw in rule_data["keywords"]:
                await self.add_keywords(rule_id, [kw["k"]], is_regex=kw["rx"], is_blacklist=kw["bl"])
                
        if "replace_rules" in rule_data:
            patterns = [rr["p"] for rr in rule_data["replace_rules"]]
            replacements = [rr["c"] for rr in rule_data["replace_rules"]]
            await self.add_replace_rules(rule_id, patterns, replacements)
            
        return {'success': True, 'message': 'Import successful'}

    @handle_errors(default_return={'success': False, 'error': 'Update summary time failed'})
    async def update_summary_time(self, rule_id: int, time: str) -> Dict[str, Any]:
        """更新总结时间并处理同步和调度"""
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        from core.helpers.common import get_main_module
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            rule.summary_time = time
            
            # 同步配置到关联规则
            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target:
                        target.summary_time = time
                        if target.is_summary:
                            main = await get_main_module()
                            if main.scheduler: await main.scheduler.schedule_rule(target)
            
            await s.commit()
            
            # 更新当前规则调度
            if rule.is_summary:
                main = await get_main_module()
                if main.scheduler: await main.scheduler.schedule_rule(rule)
                
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Update AI model failed'})
    async def update_ai_model(self, rule_id: int, model: str) -> Dict[str, Any]:
        """更新 AI 模型并处理同步"""
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            rule.ai_model = model
            
            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target: target.ai_model = model
            
            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Toggle setting failed'})
    async def toggle_rule_setting(self, rule_id: int, field: str, value: Optional[Any] = None) -> Dict[str, Any]:
        """通用的规则设置切换逻辑 (支持同步)"""
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            current_val = getattr(rule, field, None)
            if value is None:
                new_val = not current_val if isinstance(current_val, bool) else current_val
            else:
                new_val = value
                
            setattr(rule, field, new_val)
            
            # 同步配置
            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target and hasattr(target, field):
                        setattr(target, field, new_val)
            
            await s.commit()
            if rule.source_chat:
                self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
                
            return {'success': True, 'new_value': new_val}

    @handle_errors(default_return={'success': False, 'error': 'Toggle media type failed'})
    async def toggle_media_type(self, rule_id: int, media_type: str) -> Dict[str, Any]:
        """切换特定媒体类型的过滤状态 (支持同步)"""
        from models.models import ForwardRule, MediaTypes, RuleSync
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        async with self.container.db.get_session() as s:
            stmt = select(ForwardRule).options(selectinload(ForwardRule.media_types)).filter_by(id=int(rule_id))
            rule = (await s.execute(stmt)).scalar_one_or_none()
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            if not rule.media_types:
                rule.media_types = MediaTypes()
                s.add(rule.media_types)
                
            new_val = not getattr(rule.media_types, media_type, False)
            setattr(rule.media_types, media_type, new_val)
            
            # 同步到从属规则
            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target_stmt = select(ForwardRule).options(selectinload(ForwardRule.media_types)).filter_by(id=sync_obj.sync_rule_id)
                    target = (await s.execute(target_stmt)).scalar_one_or_none()
                    if target:
                        if not target.media_types:
                            target.media_types = MediaTypes()
                            s.add(target.media_types)
                        setattr(target.media_types, media_type, new_val)
            
            await s.commit()
            if rule.source_chat:
                self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
                
            return {'success': True, 'new_value': new_val}

    @handle_errors(default_return={'success': False, 'error': 'Toggle media extension failed'})
    async def toggle_media_extension(self, rule_id: int, extension: str) -> Dict[str, Any]:
        """切换特定媒体后缀的过滤状态 (支持同步)"""
        from models.models import ForwardRule, MediaExtensions, RuleSync
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        async with self.container.db.get_session() as s:
            stmt = select(ForwardRule).options(selectinload(ForwardRule.media_extensions)).filter_by(id=int(rule_id))
            rule = (await s.execute(stmt)).scalar_one_or_none()
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            # 查找现有后缀
            existing = next((ext for ext in rule.media_extensions if ext.extension == extension), None)
            
            if existing:
                await s.delete(existing)
                added = False
            else:
                new_ext = MediaExtensions(rule_id=rule.id, extension=extension)
                s.add(new_ext)
                added = True
                
            # 同步
            if rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    target_stmt = select(ForwardRule).options(selectinload(ForwardRule.media_extensions)).filter_by(id=sync_obj.sync_rule_id)
                    target = (await s.execute(target_stmt)).scalar_one_or_none()
                    if target:
                         t_existing = next((ext for ext in target.media_extensions if ext.extension == extension), None)
                         if added and not t_existing:
                             s.add(MediaExtensions(rule_id=target.id, extension=extension))
                         elif not added and t_existing:
                             await s.delete(t_existing)
            
            await s.commit()
            if rule.source_chat:
                self.container.rule_repo.clear_cache(int(rule.source_chat.telegram_chat_id))
                
            return {'success': True, 'added': added}

    @handle_errors(default_return={'success': False, 'error': 'Toggle push config setting failed'})
    async def toggle_push_config_setting(self, config_id: int, field: str) -> Dict[str, Any]:
        """切换特定推送配置的布尔设置 (支持同步)"""
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'Config not found'}
            
            rule_id = config.rule_id
            push_channel = config.push_channel
            
            new_val = not getattr(config, field, False)
            setattr(config, field, new_val)
            
            # 同步
            rule = await s.get(ForwardRule, rule_id)
            if rule and rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    # 寻找同名频道配置
                    stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(stmt)).scalar_one_or_none()
                    if target_config:
                        setattr(target_config, field, new_val)
            
            await s.commit()
            return {'success': True, 'new_value': new_val}
            
    @handle_errors(default_return={'success': False, 'error': 'Toggle media send mode failed'})
    async def toggle_media_send_mode(self, config_id: int) -> Dict[str, Any]:
        """切换推送媒体发送模式 (支持同步)"""
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config:
                return {'success': False, 'error': 'Config not found'}
            
            new_mode = "Multiple" if config.media_send_mode == "Single" else "Single"
            config.media_send_mode = new_mode
            
            # 同步
            rule = await s.get(ForwardRule, config.rule_id)
            if rule and rule.enable_sync:
                result = await s.execute(select(RuleSync).filter(RuleSync.rule_id == rule.id))
                for sync_obj in result.scalars().all():
                    stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=config.push_channel)
                    target_config = (await s.execute(stmt)).scalar_one_or_none()
                    if target_config:
                        target_config.media_send_mode = new_mode
            
            await s.commit()
            return {'success': True, 'new_mode': new_mode}

    @handle_errors(default_return={'success': False, 'error': 'Toggle rule sync failed'})
    async def toggle_rule_sync(self, source_rule_id: int, target_rule_id: int) -> Dict[str, Any]:
        """建立或撤销两条规则之间的配置同步关系"""
        from models.models import RuleSync
        from sqlalchemy import select, delete
        
        async with self.container.db.get_session() as s:
            # 检查是否已存在
            stmt = select(RuleSync).filter_by(rule_id=source_rule_id, sync_rule_id=target_rule_id)
            existing = (await s.execute(stmt)).scalar_one_or_none()
            
            if existing:
                # 存在则删除
                await s.delete(existing)
                action = "removed"
            else:
                # 不存在则创建
                new_sync = RuleSync(rule_id=source_rule_id, sync_rule_id=target_rule_id)
                s.add(new_sync)
                action = "added"
            
            await s.commit()
            return {'success': True, 'action': action}

    @handle_errors(default_return={'success': False, 'error': 'Setting current source chat failed'})
    async def set_current_source_chat(self, chat_id: int, source_telegram_id: str) -> Dict[str, Any]:
        """设置当前聊天正在管理的源聊天 ID (用于 UI 切换)"""
        from models.models import Chat
        async with self.container.db.get_session() as s:
            chat = await s.get(Chat, chat_id)
            if not chat:
                return {'success': False, 'error': 'Chat not found'}
            
            chat.current_add_id = source_telegram_id
            await s.commit()
            # 不需要清除缓存，因为这只是 UI 状态，不影响转发逻辑
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Updating AI setting failed'})
    async def update_ai_setting(self, rule_id: int, field: str, value: Any) -> Dict[str, Any]:
        """更新 AI 相关设置 (模型、时间等)，并处理同步和调度更新"""
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule:
                return {'success': False, 'error': 'Rule not found'}
            
            old_val = getattr(rule, field)
            setattr(rule, field, value)
            
            # 记录需要重新调度的规则 ID 列表
            rules_to_reschedule = [rule.id] if rule.is_summary and field == 'summary_time' else []
            
            # 同步
            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                sync_results = await s.execute(sync_stmt)
                for sync_obj in sync_results.scalars().all():
                    target = await s.get(ForwardRule, sync_obj.sync_rule_id)
                    if target and hasattr(target, field):
                        setattr(target, field, value)
                        if target.is_summary and field == 'summary_time':
                            rules_to_reschedule.append(target.id)
            
            await s.commit()
            
            # 触发调度更新 (副作用)
            if rules_to_reschedule and self.container.scheduler:
                for rid in rules_to_reschedule:
                    # 获取最新 DTO 传给调度器 (保持解耦)
                    latest_rule_dto = await self.container.rule_repo.get_by_id(rid)
                    if latest_rule_dto:
                         # 调度器目前可能直接收 DTO 或 ORM，取决于实现
                         # 这里调用 container.scheduler.schedule_rule
                         await self.container.scheduler.schedule_rule(latest_rule_dto)
            
            return {'success': True, 'old_value': old_val, 'new_value': value}

    @handle_errors(default_return={'success': False, 'error': 'Immediate summary task failed'})
    async def summary_now(self, rule_id: int) -> Dict[str, Any]:
        """立即为规则执行 AI 总结"""
        rule_dto = await self.container.rule_repo.get_by_id(rule_id)
        if not rule_dto:
            return {'success': False, 'error': 'Rule not found'}
            
        if not self.container.scheduler:
            return {'success': False, 'error': 'Scheduler not initialized'}
            
        # 启动异步任务
    @handle_errors(default_return={'success': False, 'error': 'Toggle media type failed'})
    async def toggle_media_type(self, rule_id: int, media_type: str) -> Dict[str, Any]:
        """切换媒体类型屏蔽状态 (支持同步)"""
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            # 使用现有 Repository/DBOps 逻辑切换
            success, msg = await self.container.rule_repo.toggle_media_type(s, rule.id, media_type)
            if not success: return {'success': False, 'error': msg}
            
            # 获取新状态
            _, _, media_types_obj = await self.container.rule_repo.get_media_types(s, rule.id)
            new_status = getattr(media_types_obj, media_type)
            
            # 同步
            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    # 强制设置同步目标的该类型状态与主规则一致
                    await self.container.rule_repo.set_media_type_status(s, sync_obj.sync_rule_id, media_type, new_status)
            
            await s.commit()
            return {'success': True, 'new_status': new_status}

    @handle_errors(default_return={'success': False, 'error': 'Toggle media extension failed'})
    async def toggle_media_extension(self, rule_id: int, extension: str) -> Dict[str, Any]:
        """切换扩展名过滤状态 (支持同步)"""
        from models.models import ForwardRule, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            rule = await s.get(ForwardRule, int(rule_id))
            if not rule: return {'success': False, 'error': 'Rule not found'}
            
            # 获取当前状态
            exts = await self.container.rule_repo.get_media_extensions(s, rule.id)
            is_selected = any(e['extension'] == extension for e in exts)
            
            if is_selected:
                # 移除
                ext_id = next((e['id'] for e in exts if e['extension'] == extension), None)
                if ext_id:
                    success, msg = await self.container.rule_repo.delete_media_extensions(s, rule.id, [ext_id])
                else:
                    success, msg = True, "Already removed"
            else:
                # 添加
                success, msg = await self.container.rule_repo.add_media_extensions(s, rule.id, [extension])
                
            if not success: return {'success': False, 'error': msg}
            
            # 同步
            if rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    if is_selected:
                        await self.container.rule_repo.remove_extension_from_rule(s, sync_obj.sync_rule_id, extension)
                    else:
                        await self.container.rule_repo.add_media_extensions(s, sync_obj.sync_rule_id, [extension])
            
            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Toggle push config status failed'})
    async def toggle_push_status_by_config(self, config_id: int) -> Dict[str, Any]:
        """切换推送配置的启用状态 (支持同步)"""
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'PushConfig not found'}
            
            config.enable_push_channel = not config.enable_push_channel
            new_status = config.enable_push_channel
            push_channel = config.push_channel
            
            # 同步
            rule = await s.get(ForwardRule, config.rule_id)
            if rule and rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    target_config_stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(target_config_stmt)).scalar_one_or_none()
                    if target_config:
                        target_config.enable_push_channel = new_status
            
            await s.commit()
            return {'success': True, 'new_value': new_status}

    @handle_errors(default_return={'success': False, 'error': 'Delete push config failed'})
    async def delete_push_config(self, config_id: int) -> Dict[str, Any]:
        """删除推送配置 (支持同步)"""
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'PushConfig not found'}
            
            rule_id = config.rule_id
            push_channel = config.push_channel
            
            # 同步删除
            rule = await s.get(ForwardRule, rule_id)
            if rule and rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    target_config_stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(target_config_stmt)).scalar_one_or_none()
                    if target_config:
                        await s.delete(target_config)
            
            await s.delete(config)
            await s.commit()
            return {'success': True}

    @handle_errors(default_return={'success': False, 'error': 'Update push config setting failed'})
    async def update_push_config_setting(self, config_id: int, field: str, value: Any) -> Dict[str, Any]:
        """更新推送配置属性 (支持同步)"""
        from models.models import ForwardRule, PushConfig, RuleSync
        from sqlalchemy import select
        
        async with self.container.db.get_session() as s:
            config = await s.get(PushConfig, int(config_id))
            if not config: return {'success': False, 'error': 'PushConfig not found'}
            
            setattr(config, field, value)
            push_channel = config.push_channel
            
            # 同步
            rule = await s.get(ForwardRule, config.rule_id)
            if rule and rule.enable_sync:
                sync_stmt = select(RuleSync).filter_by(rule_id=rule.id)
                results = await s.execute(sync_stmt)
                for sync_obj in results.scalars().all():
                    target_config_stmt = select(PushConfig).filter_by(rule_id=sync_obj.sync_rule_id, push_channel=push_channel)
                    target_config = (await s.execute(target_config_stmt)).scalar_one_or_none()
                    if target_config and hasattr(target_config, field):
                        setattr(target_config, field, value)
            
            await s.commit()
            return {'success': True}
