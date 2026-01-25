import logging
import re
from typing import List, Optional, Any
from enums.enums import ForwardMode
from utils.processing.ac_automaton import ACManager

logger = logging.getLogger(__name__)

class RuleFilterService:
    """
    转发规则过滤服务
    处理关键词匹配、模式处理等核心过滤逻辑
    """
    
    @staticmethod
    async def check_keywords(rule: Any, message_text: str, event: Any = None) -> bool:
        """
        检查消息是否匹配关键字规则
        
        Args:
            rule: 转发规则 DTO 或 ORM
            message_text: 消息文本
            event: 可选的消息事件对象
            
        Returns:
            bool: 是否应该转发消息
        """
        from services.user_service import user_service
        
        reverse_blacklist = getattr(rule, 'enable_reverse_blacklist', False)
        reverse_whitelist = getattr(rule, 'enable_reverse_whitelist', False)
        
        # 合并媒体文件名等可检索信息
        try:
            if event and hasattr(event, "message") and getattr(event.message, "media", None):
                doc = getattr(event.message, "document", None)
                if doc and hasattr(doc, "attributes") and doc.attributes:
                    for attr in doc.attributes:
                        file_name = getattr(attr, "file_name", None)
                        if file_name:
                            if file_name not in (message_text or ""):
                                message_text = f"{message_text}\n{file_name}" if message_text else file_name
                            break
        except Exception:
            pass

        # 处理用户信息过滤
        if getattr(rule, 'is_filter_user_info', False) and event:
            message_text = await user_service.process_user_info(event, rule.id, message_text)

        forward_mode = rule.forward_mode
        
        if forward_mode == ForwardMode.WHITELIST:
            return await RuleFilterService.process_whitelist_mode(rule, message_text, reverse_blacklist)
        elif forward_mode == ForwardMode.BLACKLIST:
            return await RuleFilterService.process_blacklist_mode(rule, message_text, reverse_whitelist)
        elif forward_mode == ForwardMode.WHITELIST_THEN_BLACKLIST:
            return await RuleFilterService.process_whitelist_then_blacklist_mode(rule, message_text, reverse_blacklist)
        elif forward_mode == ForwardMode.BLACKLIST_THEN_WHITELIST:
            return await RuleFilterService.process_blacklist_then_whitelist_mode(rule, message_text, reverse_whitelist)

        logger.error(f"未知的转发模式: {forward_mode}")
        return False

    @staticmethod
    async def process_whitelist_mode(rule: Any, message_text: str, reverse_blacklist: bool) -> bool:
        should_forward = False
        whitelist_keywords = [k for k in rule.keywords if not k.is_blacklist]
        if await RuleFilterService.check_keywords_fast(whitelist_keywords, message_text, rule.id):
            should_forward = True

        if not should_forward:
            return False

        if reverse_blacklist:
            reversed_blacklist = [k for k in rule.keywords if k.is_blacklist]
            if reversed_blacklist:
                if not await RuleFilterService.check_keywords_fast(reversed_blacklist, message_text, rule.id):
                    return False
        return True

    @staticmethod
    async def process_blacklist_mode(rule: Any, message_text: str, reverse_whitelist: bool) -> bool:
        blacklist_keywords = [k for k in rule.keywords if k.is_blacklist]
        if await RuleFilterService.check_keywords_fast(blacklist_keywords, message_text, rule.id):
            return False

        if reverse_whitelist:
            reversed_whitelist = [k for k in rule.keywords if not k.is_blacklist]
            if await RuleFilterService.check_keywords_fast(reversed_whitelist, message_text, rule.id):
                return False
        return True

    @staticmethod
    async def process_whitelist_then_blacklist_mode(rule: Any, message_text: str, reverse_blacklist: bool) -> bool:
        whitelist_keywords = [k for k in rule.keywords if not k.is_blacklist]
        if not await RuleFilterService.check_keywords_fast(whitelist_keywords, message_text, rule.id):
            return False
            
        blacklist_keywords = [k for k in rule.keywords if k.is_blacklist]
        if reverse_blacklist:
            if not await RuleFilterService.check_keywords_fast(blacklist_keywords, message_text, rule.id):
                return False
        else:
            if await RuleFilterService.check_keywords_fast(blacklist_keywords, message_text, rule.id):
                return False
        return True

    @staticmethod
    async def process_blacklist_then_whitelist_mode(rule: Any, message_text: str, reverse_whitelist: bool) -> bool:
        blacklist_keywords = [k for k in rule.keywords if k.is_blacklist]
        if await RuleFilterService.check_keywords_fast(blacklist_keywords, message_text, rule.id):
            return False

        whitelist_keywords = [k for k in rule.keywords if not k.is_blacklist]
        if reverse_whitelist:
            if await RuleFilterService.check_keywords_fast(whitelist_keywords, message_text, rule.id):
                return False
        else:
            if not await RuleFilterService.check_keywords_fast(whitelist_keywords, message_text, rule.id):
                return False
        return True

    @staticmethod
    async def check_keywords_fast(keywords: List[Any], message_text: str, rule_id: Optional[int] = None) -> bool:
        if not keywords or not message_text:
            return False

        fixed_kws = []
        regex_kws = []
        for k in keywords:
            if getattr(k, 'is_regex', False):
                regex_kws.append(k)
            else:
                fixed_kws.append(k)
                
        for k in regex_kws:
            try:
                if re.search(k.keyword, message_text, re.I):
                    return True
            except Exception as e:
                logger.error(f"正则匹配出错: {k.keyword}, {e}")
                
        if fixed_kws:
            kw_list = [k.keyword.lower() for k in fixed_kws]
            try:
                target_id = rule_id or hash(tuple(kw_list))
                ac = ACManager.get_automaton(target_id, kw_list)
                if ac.has_any_match(message_text.lower()):
                    return True
            except Exception as e:
                logger.error(f"AC自动机匹配出错: {e}")
                for kw in fixed_kws:
                    if kw.keyword.lower() in message_text.lower():
                        return True
                        
        return False
