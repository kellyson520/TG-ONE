from pydantic import BaseModel, Field
from typing import List, Optional

class KeywordAddRequest(BaseModel):
    keywords: List[str]
    is_regex: bool = False
    is_negative: bool = False
    case_sensitive: bool = False

class ReplaceRuleAddRequest(BaseModel):
    pattern: str
    replacement: str
    is_regex: bool = False

class RuleCreateRequest(BaseModel):
    source_chat_id: str
    target_chat_id: str
    enabled: bool = True
    enable_dedup: bool = False

class RuleUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    enable_dedup: Optional[bool] = None
    target_chat_id: Optional[str] = None
    use_bot: Optional[bool] = None
    force_pure_forward: Optional[bool] = None
    is_original_link: Optional[bool] = None
    is_original_sender: Optional[bool] = None
    is_original_time: Optional[bool] = None
    is_delete_original: Optional[bool] = None
    enable_delay: Optional[bool] = None
    delay_seconds: Optional[int] = None
    enable_media_size_filter: Optional[bool] = None
    max_media_size: Optional[int] = None
    enable_media_type_filter: Optional[bool] = None
    is_ai: Optional[bool] = None
    ai_model: Optional[str] = None
    ai_prompt: Optional[str] = None
    description: Optional[str] = None
