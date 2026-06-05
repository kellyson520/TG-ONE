import logging
from datetime import datetime, timezone
from typing import Dict, Any
from models.models import ForwardRule, RuleLog

logger = logging.getLogger(__name__)

class RuleDTOMapper:
    @staticmethod
    def to_dict(rule: ForwardRule, stats: Dict[str, int] = None) -> Dict[str, Any]:
        if not stats:
            stats = {'processed': 0, 'forwarded': 0, 'error': 0}
            
        return {
            "id": rule.id,
            "source_chat_id": rule.source_chat_id,
            "target_chat_id": rule.target_chat_id,
            "enabled": rule.enable_rule,
            "enable_dedup": rule.enable_dedup,
            "forward_mode": str(rule.forward_mode.value if hasattr(rule.forward_mode, 'value') else rule.forward_mode),
            "use_bot": rule.use_bot,
            "message_mode": str(rule.message_mode.value if hasattr(rule.message_mode, 'value') else rule.message_mode),
            "is_replace": rule.is_replace,
            "is_preview": str(rule.is_preview.value if hasattr(rule.is_preview, 'value') else rule.is_preview),
            "is_original_link": rule.is_original_link,
            "is_delete_original": rule.is_delete_original,
            "is_original_sender": rule.is_original_sender,
            "is_original_time": rule.is_original_time,
            "force_pure_forward": rule.force_pure_forward,
            "enable_delay": rule.enable_delay,
            "delay_seconds": rule.delay_seconds,
            "max_media_size": rule.max_media_size,
            "enable_media_size_filter": rule.enable_media_size_filter,
            "enable_media_type_filter": rule.enable_media_type_filter,
            "is_ai": rule.is_ai,
            "ai_model": rule.ai_model,
            "ai_prompt": rule.ai_prompt,
            "description": rule.description,
            "priority": rule.priority,
            "created_at": rule.created_at.replace(tzinfo=timezone.utc).isoformat() if isinstance(rule.created_at, datetime) else rule.created_at,
            "updated_at": rule.updated_at.replace(tzinfo=timezone.utc).isoformat() if isinstance(rule.updated_at, datetime) else rule.updated_at,
            "forwards": stats.get('forwarded', 0),  
            "processed": stats.get('processed', 0),
            "errors": stats.get('error', 0),
            "keywords_count": len(rule.keywords) if rule.keywords else 0,
            "replace_rules_count": len(rule.replace_rules) if rule.replace_rules else 0,
            "source_chat": {
                "id": rule.source_chat.id,
                "title": rule.source_chat.title or rule.source_chat.name,
                "telegram_chat_id": rule.source_chat.telegram_chat_id,
                "username": rule.source_chat.username
            } if rule.source_chat else None,
            "target_chat": {
                "id": rule.target_chat.id,
                "title": rule.target_chat.title or rule.target_chat.name,
                "telegram_chat_id": rule.target_chat.telegram_chat_id,
                "username": rule.target_chat.username
            } if rule.target_chat else None,
        }
        
    @staticmethod
    def to_detail_dict(rule: ForwardRule, stats: Dict[str, int] = None) -> Dict[str, Any]:
        data = RuleDTOMapper.to_dict(rule, stats)
        # Add lists
        data["keywords"] = [
            {"id": kw.id, "keyword": kw.keyword, "is_regex": kw.is_regex, "is_blacklist": getattr(kw, 'is_blacklist', False)}
            for kw in (rule.keywords or [])
        ]
        data["replace_rules"] = [
            {"id": rr.id, "pattern": rr.pattern, "content": rr.content}
            for rr in (rule.replace_rules or [])
        ]
        return data

    @staticmethod
    def log_to_dict(item: RuleLog) -> Dict[str, Any]:
        source_title = "Unknown"
        target_title = "Unknown"
        try:
             if item.rule:
                if item.rule.source_chat:
                    chat = item.rule.source_chat
                    source_title = chat.title or chat.name or chat.username or str(chat.telegram_chat_id)
                if item.rule.target_chat:
                    chat = item.rule.target_chat
                    target_title = chat.title or chat.name or chat.username or str(chat.telegram_chat_id)
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

        return {
            'id': item.id,
            'rule_id': item.rule_id,
            'source_message_id': item.message_id,
            'message_text': item.message_text,
            'message_type': item.message_type,
            'processing_time': item.processing_time,
            'action': item.action,
            'result': item.details,
            'error_message': item.details if item.action in ('error', 'filtered') else None,
            'created_at': item.created_at.replace(tzinfo=timezone.utc).isoformat() if isinstance(item.created_at, datetime) else item.created_at,
            'source_chat': source_title,
            'target_chat': target_title
        }
