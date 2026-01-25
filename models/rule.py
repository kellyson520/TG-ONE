from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class ForwardRule(Base):
    __tablename__ = 'forward_rules'
    id = Column(Integer, primary_key=True)
    source_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    target_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    
    # 基础设置
    enable_rule = Column(Boolean, default=True)
    forward_mode = Column(String, default='blacklist') # Match ForwardMode.BLACKLIST.value
    handle_mode = Column(String, default='FORWARD') # Match HandleMode.FORWARD.value
    message_mode = Column(String, default='Markdown') # Match MessageMode.MARKDOWN.value
    
    # 功能开关
    enable_dedup = Column(Boolean, default=False)
    is_ai = Column(Boolean, default=False)
    is_summary = Column(Boolean, default=False)
    is_delete_original = Column(Boolean, default=False)
    is_preview = Column(String, default='follow') # Match PreviewMode.FOLLOW.value
    is_original_sender = Column(Boolean, default=False)
    is_original_time = Column(Boolean, default=False)
    is_original_link = Column(Boolean, default=False)
    is_filter_user_info = Column(Boolean, default=False)
    
    # 进阶特性
    use_bot = Column(Boolean, default=True)
    enable_comment_button = Column(Boolean, default=False)
    enable_delay = Column(Boolean, default=False)
    delay_seconds = Column(Integer, default=5)
    force_pure_forward = Column(Boolean, default=False)
    enable_sync = Column(Boolean, default=False)
    
    # 反转逻辑
    enable_reverse_blacklist = Column(Boolean, default=False)
    enable_reverse_whitelist = Column(Boolean, default=False)
    
    # 提示词
    ai_prompt = Column(Text, nullable=True)
    summary_prompt = Column(Text, nullable=True)
    
    # 额外字段 (为 DTO 补全)
    userinfo_template = Column(String, default='**{name}**')
    time_template = Column(String, default='{time}')
    original_link_template = Column(String, default='原始连接：{original_link}')
    add_mode = Column(String, default='blacklist') # Match AddMode.BLACKLIST.value
    
    # 元数据
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat())
    created_by = Column(String, nullable=True)
    message_count = Column(Integer, default=0)
    last_used = Column(String, nullable=True)

    # Relationships
    source_chat = relationship('Chat', foreign_keys=[source_chat_id], back_populates='source_rules')
    target_chat = relationship('Chat', foreign_keys=[target_chat_id], back_populates='target_rules')
    keywords = relationship('Keyword', back_populates='rule', cascade="all, delete-orphan")
    replace_rules = relationship('ReplaceRule', back_populates='rule', cascade="all, delete-orphan")
    media_types = relationship('MediaTypes', back_populates='rule', uselist=False, cascade="all, delete-orphan")
    media_extensions = relationship('MediaExtensions', back_populates='rule', cascade="all, delete-orphan")
    rule_syncs = relationship('RuleSync', back_populates='rule', cascade="all, delete-orphan")
    push_config = relationship('PushConfig', back_populates='rule', uselist=False, cascade="all, delete-orphan")
    rss_config = relationship('RSSConfig', back_populates='rule', uselist=False, cascade="all, delete-orphan")
    rule_statistics = relationship('RuleStatistics', back_populates='rule', cascade="all, delete-orphan")
    rule_logs = relationship('RuleLog', back_populates='rule', cascade="all, delete-orphan")

class ForwardMapping(Base):
    """多对多转发表"""
    __tablename__ = 'forward_mappings'
    id = Column(Integer, primary_key=True)
    source_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    target_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=True)
    enabled = Column(Boolean, default=True)
    
    source_chat = relationship('Chat', foreign_keys=[source_chat_id])
    target_chat = relationship('Chat', foreign_keys=[target_chat_id])
    rule = relationship('ForwardRule')

class Keyword(Base):
    __tablename__ = 'keywords'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    keyword = Column(String, nullable=True)
    is_regex = Column(Boolean, default=False)
    is_blacklist = Column(Boolean, default=True) # Default to Blacklist
    
    rule = relationship('ForwardRule', back_populates='keywords')
    __table_args__ = (
        UniqueConstraint('rule_id', 'keyword','is_regex','is_blacklist', name='unique_rule_keyword_is_regex_is_blacklist'),
    )

class ReplaceRule(Base):
    __tablename__ = 'replace_rules'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    pattern = Column(String, nullable=False)
    content = Column(String, nullable=True)
    
    rule = relationship('ForwardRule', back_populates='replace_rules')
    __table_args__ = (
        UniqueConstraint('rule_id', 'pattern', 'content', name='unique_rule_pattern_content'),
    )

class MediaTypes(Base):
    __tablename__ = 'media_types'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, unique=True)
    photo = Column(Boolean, default=False)
    document = Column(Boolean, default=False)
    video = Column(Boolean, default=False)
    audio = Column(Boolean, default=False)
    voice = Column(Boolean, default=False)
    
    rule = relationship('ForwardRule', back_populates='media_types')

class MediaExtensions(Base):
    __tablename__ = 'media_extensions'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    extension = Column(String, nullable=False)
    
    rule = relationship('ForwardRule', back_populates='media_extensions')
    __table_args__ = (
        UniqueConstraint('rule_id', 'extension', name='unique_rule_extension'),
    )

class RuleSync(Base):
    __tablename__ = 'rule_syncs'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    sync_rule_id = Column(Integer, nullable=False)
    
    rule = relationship('ForwardRule', back_populates='rule_syncs')

class PushConfig(Base):
    __tablename__ = 'push_configs'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    enable_push_channel = Column(Boolean, default=False)
    push_channel = Column(String, nullable=True) # Make nullable as it might be missing
    media_send_mode = Column(String, nullable=False, default='Single')
    
    rule = relationship('ForwardRule', back_populates='push_config')

class RSSConfig(Base):
    __tablename__ = 'rss_configs'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, unique=True)
    enable_rss = Column(Boolean, default=False)
    rss_url = Column(String, nullable=True) # Make nullable
    check_interval = Column(Integer, default=600)
    last_check_at = Column(DateTime, nullable=True)
    
    rule = relationship('ForwardRule', back_populates='rss_config')
    patterns = relationship('RSSPattern', back_populates='rss_config', cascade="all, delete-orphan")

class RSSPattern(Base):
    __tablename__ = 'rss_patterns'
    id = Column(Integer, primary_key=True)
    rss_config_id = Column(Integer, ForeignKey('rss_configs.id'), nullable=False)
    pattern = Column(String, nullable=False)
    pattern_type = Column(String, nullable=False) # title, content, link
    priority = Column(Integer, default=0)
    
    rss_config = relationship('RSSConfig', back_populates='patterns')
    __table_args__ = (
        UniqueConstraint('rss_config_id', 'pattern', 'pattern_type', name='unique_rss_pattern'),
    )
