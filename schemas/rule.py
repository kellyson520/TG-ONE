from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Union
from .common import TimestampMixin
from enums.enums import ForwardMode, PreviewMode, MessageMode, AddMode, HandleMode

# --- Component Schemas ---

class MediaTypeDTO(BaseModel):
    photo: bool = False
    document: bool = False
    video: bool = False
    audio: bool = False
    voice: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class MediaExtensionDTO(BaseModel):
    extension: str
    
    model_config = ConfigDict(from_attributes=True)

class KeywordDTO(BaseModel):
    keyword: str
    is_regex: bool = False
    is_blacklist: bool = True
    
    model_config = ConfigDict(from_attributes=True)

class ReplaceRuleDTO(BaseModel):
    pattern: str
    content: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class PushConfigDTO(BaseModel):
    enable_push_channel: bool = False
    push_channel: str
    media_send_mode: str = 'Single'
    
    model_config = ConfigDict(from_attributes=True)

class RSSPatternDTO(BaseModel):
    pattern: str
    pattern_type: str
    priority: int = 0
    
    model_config = ConfigDict(from_attributes=True)

class RSSConfigDTO(BaseModel):
    enable_rss: bool = False
    rule_title: Optional[str] = None
    rule_description: Optional[str] = None
    language: str = 'zh-CN'
    max_items: int = 50
    is_auto_title: bool = False
    is_auto_content: bool = False
    is_ai_extract: bool = False
    ai_extract_prompt: Optional[str] = None
    is_auto_markdown_to_html: bool = False
    enable_custom_title_pattern: bool = False
    enable_custom_content_pattern: bool = False
    patterns: List[RSSPatternDTO] = []
    
    model_config = ConfigDict(from_attributes=True)

# --- Rule Schemas ---

class RuleBase(BaseModel):
    source_chat_id: int
    target_chat_id: int
    forward_mode: ForwardMode = ForwardMode.BLACKLIST
    use_bot: bool = True
    message_mode: MessageMode = MessageMode.MARKDOWN
    is_replace: bool = False
    is_preview: PreviewMode = PreviewMode.FOLLOW
    is_original_link: bool = False
    is_ufb: bool = False
    ufb_domain: Optional[str] = None
    ufb_item: Optional[str] = 'main'
    is_delete_original: bool = False
    is_original_sender: bool = False
    userinfo_template: str = '**{name}**'
    time_template: str = '{time}'
    original_link_template: str = '原始连接：{original_link}'
    is_original_time: bool = False
    add_mode: AddMode = AddMode.BLACKLIST
    enable_rule: bool = True
    is_filter_user_info: bool = False
    handle_mode: HandleMode = HandleMode.FORWARD
    message_thread_id: Optional[int] = None
    enable_comment_button: bool = False
    enable_media_type_filter: bool = False
    required_sender_id: Optional[str] = None
    required_sender_regex: Optional[str] = None
    enable_media_size_filter: bool = False
    max_media_size: int = 50 # Default from settings
    is_send_over_media_size_message: bool = True
    enable_extension_filter: bool = False
    extension_filter_mode: AddMode = AddMode.BLACKLIST
    is_save_to_local: bool = False
    
    # Precise Media Filter
    enable_duration_filter: bool = False
    min_duration: int = 0
    max_duration: int = 0
    enable_resolution_filter: bool = False
    min_width: int = 0
    max_width: int = 0
    min_height: int = 0
    max_height: int = 0
    enable_file_size_range: bool = False
    min_file_size: int = 0
    max_file_size: int = 0
    
    enable_reverse_blacklist: bool = False
    enable_reverse_whitelist: bool = False
    media_allow_text: bool = False
    
    enable_push: bool = False
    enable_only_push: bool = False
    
    force_pure_forward: bool = False
    enable_dedup: bool = False
    allow_delete_source_on_dedup: bool = False
    
    # AI
    is_ai: bool = False
    ai_model: Optional[str] = None
    ai_prompt: Optional[str] = None
    enable_ai_upload_image: bool = False
    is_summary: bool = False
    summary_time: str = "08:00"
    summary_prompt: Optional[str] = None
    is_keyword_after_ai: bool = False
    is_top_summary: bool = True
    
    enable_delay: bool = False
    delay_seconds: int = 5
    
    only_rss: bool = False
    enable_sync: bool = False
    
    unique_key: Optional[str] = None
    priority: int = 0
    description: Optional[str] = None
    daily_limit: Optional[int] = None
    rate_limit: Optional[int] = None
    webhook_url: Optional[str] = None
    custom_config: Optional[str] = None

class RuleCreate(RuleBase):
    pass

class RuleUpdate(BaseModel):
    # Support partial update
    # In practice, we might use RuleBase fields as optional
    # For now, allow everything optional
    pass 

from .chat import ChatDTO

class RuleDTO(RuleBase, TimestampMixin):
    id: int
    created_by: Optional[str] = None
    message_count: int = 0
    last_used: Optional[str] = None
    
    # Relationships
    source_chat: Optional[ChatDTO] = None
    target_chat: Optional[ChatDTO] = None
    
    keywords: List[KeywordDTO] = []
    replace_rules: List[ReplaceRuleDTO] = []
    media_types: Optional[MediaTypeDTO] = None
    media_extensions: List[MediaExtensionDTO] = [] 
    push_config: Optional[PushConfigDTO] = None
    rss_config: Optional[RSSConfigDTO] = None

    model_config = ConfigDict(from_attributes=True)
