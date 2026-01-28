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
        """复制规则 (Logic Port from original service)"""
        if not target_rule_id:
             return {'success': False, 'error': 'Target Rule ID required'}
             
        # Use Repository to get ORM for deep modification (internal Service use only)
        source_rule = await self.container.rule_repo.get_full_rule_orm(source_rule_id)
        if not source_rule:
            return {'success': False, 'error': f'Source rule {source_rule_id} not found'}
            
        target_rule = await self.container.rule_repo.get_full_rule_orm(target_rule_id)
        if not target_rule:
            return {'success': False, 'error': f'Target rule {target_rule_id} not found'}

        # Copy settings
        exclude_cols = {'id', 'source_chat_id', 'target_chat_id', 'created_at', 'updated_at'}
        for column in source_rule.__table__.columns:
            if column.name not in exclude_cols:
                setattr(target_rule, column.name, getattr(source_rule, column.name))

        # Copy associations (Keywords, ReplaceRules, etc.)
        # Clear existing
        target_rule.keywords.clear()
        target_rule.replace_rules.clear()
        
        # Re-add from source
        from models.models import Keyword, ReplaceRule
        for kw in source_rule.keywords:
            target_rule.keywords.append(Keyword(
                keyword=kw.keyword,
                is_regex=kw.is_regex,
                is_blacklist=kw.is_blacklist
            ))
        for rr in source_rule.replace_rules:
            target_rule.replace_rules.append(ReplaceRule(
                pattern=rr.pattern,
                content=rr.content
            ))
            
        await self.container.rule_repo.save_rule(target_rule)
        self.container.rule_repo.clear_cache(int(target_rule.source_chat.telegram_chat_id))
        
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
            await self.container.rule_repo.create_rule(
                source_chat_id=source_chat_obj.id,
                target_chat_id=target_chat_obj.id,
                enable_rule=True,
                forward_mode=ForwardMode.BLACKLIST,
                created_at=datetime.utcnow()
            )
            is_new = True
            rule_id = "New" 
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
        pass
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
