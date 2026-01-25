from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Enum, UniqueConstraint, inspect, text, event, select, DateTime, Text
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from enums.enums import ForwardMode, PreviewMode, MessageMode, AddMode, HandleMode
import logging
from datetime import datetime
from pathlib import Path
import os
from core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

class Chat(Base):
    __tablename__ = 'chats'

    id = Column(Integer, primary_key=True)
    telegram_chat_id = Column(String, unique=True, nullable=False, index=True)  # 添加索引
    name = Column(String, nullable=True)
    username = Column(String, nullable=True)  # Telegram 用户名
    current_add_id = Column(String, nullable=True)
    # 新增字段
    chat_type = Column(String, nullable=True)  # 聊天类型：channel, group, supergroup, private
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    is_active = Column(Boolean, default=True)  # 是否活跃
    member_count = Column(Integer, nullable=True)  # 成员数量
    description = Column(String, nullable=True)  # 聊天描述

    # 关系
    source_rules = relationship('ForwardRule', foreign_keys='ForwardRule.source_chat_id', back_populates='source_chat')
    target_rules = relationship('ForwardRule', foreign_keys='ForwardRule.target_chat_id', back_populates='target_chat')
    # 新增关系
    chat_stats = relationship('ChatStatistics', back_populates='chat', cascade="all, delete-orphan")

class ForwardRule(Base):
    __tablename__ = 'forward_rules'

    id = Column(Integer, primary_key=True)
    source_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    target_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    forward_mode = Column(Enum(ForwardMode), nullable=False, default=ForwardMode.BLACKLIST)
    use_bot = Column(Boolean, default=True)
    message_mode = Column(Enum(MessageMode), nullable=False, default=MessageMode.MARKDOWN)
    is_replace = Column(Boolean, default=False)
    is_preview = Column(Enum(PreviewMode), nullable=False, default=PreviewMode.FOLLOW)  # 三个值，开，关，按照原消息
    is_original_link = Column(Boolean, default=False)   # 是否附带原消息链接
    is_ufb = Column(Boolean, default=False)
    ufb_domain = Column(String, nullable=True)
    ufb_item = Column(String, nullable=True,default='main')
    is_delete_original = Column(Boolean, default=False)  # 是否删除原始消息
    is_original_sender = Column(Boolean, default=False)  # 是否附带原始消息发送人名称
    userinfo_template = Column(String, default='**{name}**', nullable=True)  # 用户信息模板
    time_template = Column(String, default='{time}', nullable=True)  # 时间模板
    original_link_template = Column(String, default='原始连接：{original_link}', nullable=True)  # 原始链接模板
    is_original_time = Column(Boolean, default=False)  # 是否附带原始消息发送时间
    add_mode = Column(Enum(AddMode), nullable=False, default=AddMode.BLACKLIST) # 添加模式,默认黑名单
    enable_rule = Column(Boolean, default=True)  # 是否启用规则
    is_filter_user_info = Column(Boolean, default=False)  # 是否过滤用户信息
    handle_mode = Column(Enum(HandleMode), nullable=False, default=HandleMode.FORWARD) # 处理模式,编辑模式和转发模式，默认转发
    message_thread_id = Column(Integer, nullable=True) # 话题组ID
    enable_comment_button = Column(Boolean, default=False)  # 是否添加对应消息的评论区直达按钮
    enable_media_type_filter = Column(Boolean, default=False)  # 是否启用媒体类型过滤
    # 发送者过滤（新增软/硬字段）
    required_sender_id = Column(String, nullable=True)
    required_sender_regex = Column(String, nullable=True)
    enable_media_size_filter = Column(Boolean, default=False)  # 是否启用媒体大小过滤
    max_media_size = Column(Integer, default=settings.DEFAULT_MAX_MEDIA_SIZE)  # 媒体大小限制，单位MB
    is_send_over_media_size_message = Column(Boolean, default=True)  # 超过限制的媒体是否发送提示消息
    enable_extension_filter = Column(Boolean, default=False)  # 是否启用媒体扩展名过滤
    extension_filter_mode = Column(Enum(AddMode), nullable=False, default=AddMode.BLACKLIST)  # 媒体扩展名过滤模式，默认黑名单
    is_save_to_local = Column(Boolean, default=False)
    
    # 新增精确媒体筛选字段
    enable_duration_filter = Column(Boolean, default=False)  # 是否启用时长过滤
    min_duration = Column(Integer, default=0)  # 最小时长（秒）
    max_duration = Column(Integer, default=0)  # 最大时长（秒，0表示无限制）
    enable_resolution_filter = Column(Boolean, default=False)  # 是否启用分辨率过滤
    min_width = Column(Integer, default=0)  # 最小宽度
    max_width = Column(Integer, default=0)  # 最大宽度（0表示无限制）
    min_height = Column(Integer, default=0)  # 最小高度
    max_height = Column(Integer, default=0)  # 最大高度（0表示无限制）
    enable_file_size_range = Column(Boolean, default=False)  # 是否启用文件大小范围过滤
    min_file_size = Column(Integer, default=0)  # 最小文件大小（KB）
    max_file_size = Column(Integer, default=0)  # 最大文件大小（KB，0表示无限制）
    enable_reverse_blacklist = Column(Boolean, default=False)  # 是否反转黑名单
    enable_reverse_whitelist = Column(Boolean, default=False)  # 是否反转白名单
    media_allow_text = Column(Boolean, default=False)  # 是否放行文本
    # 推送相关字段
    enable_push = Column(Boolean, default=False)  # 是否启用推送
    enable_only_push = Column(Boolean, default=False)  # 是否只转发到推送配置
    # 纯转发开关：启用后在发送阶段强制使用 forward 消息（不下载后上传发送）
    force_pure_forward = Column(Boolean, default=False)
    # 去重开关：启用后在发送前检查目标会话内是否有重复媒体
    enable_dedup = Column(Boolean, default=False)
    # 去重时是否尝试删除源群消息（需要在源群有管理删除权限）
    allow_delete_source_on_dedup = Column(Boolean, default=False)

    # AI相关字段
    is_ai = Column(Boolean, default=False)  # 是否启用AI处理
    ai_model = Column(String, nullable=True)  # 使用的AI模型
    ai_prompt = Column(String, nullable=True)  # AI处理的prompt
    enable_ai_upload_image = Column(Boolean, default=False)  # 是否启用AI图片上传功能
    is_summary = Column(Boolean, default=False)  # 是否启用AI总结
    summary_time = Column(String(5), default=settings.DEFAULT_SUMMARY_TIME)
    summary_prompt = Column(String, nullable=True)  # AI总结的prompt
    is_keyword_after_ai = Column(Boolean, default=False) # AI处理后是否再次执行关键字过滤
    is_top_summary = Column(Boolean, default=True) # 是否顶置总结消息
    enable_delay = Column(Boolean, default=False)  # 是否启用延迟处理
    delay_seconds = Column(Integer, default=5)  # 延迟处理秒数
    # RSS相关字段
    only_rss = Column(Boolean, default=False)  # 是否只转发RSS
    # 同步功能相关
    enable_sync = Column(Boolean, default=False)  # 是否启用规则同步功能
    
    # 新增管理字段
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    unique_key = Column(String, unique=True, index=True, nullable=True)
    grouped_id = Column(String, index=True, nullable=True)  # 新增：用于聚合媒体组任务  # 创建者
    created_by = Column(String, nullable=True)  # 创建者
    priority = Column(Integer, default=0)  # 规则优先级（数字越大越优先）
    description = Column(String, nullable=True)  # 规则描述
    
    # 统计字段
    message_count = Column(Integer, default=0)  # 已处理消息数
    last_used = Column(String, nullable=True)  # 最后使用时间
    
    # 限制字段
    daily_limit = Column(Integer, nullable=True)  # 每日消息限制
    rate_limit = Column(Integer, nullable=True)  # 速率限制（每分钟）
    
    # 高级功能
    webhook_url = Column(String, nullable=True)  # Webhook 回调地址
    custom_config = Column(String, nullable=True)  # 自定义配置（JSON格式）
    
    # 过滤器链配置
    enabled_filters = Column(String, nullable=True)  # 启用的过滤器链配置（JSON格式）
    user_mode_filters = Column(String, nullable=True)  # 用户模式专用过滤器配置（JSON格式）

    # 添加索引和约束
    __table_args__ = (
        UniqueConstraint('source_chat_id', 'target_chat_id', name='unique_source_target'),
        # 添加复合索引
    )

    # 关系
    source_chat = relationship('Chat', foreign_keys=[source_chat_id], back_populates='source_rules')
    target_chat = relationship('Chat', foreign_keys=[target_chat_id], back_populates='target_rules')
    keywords = relationship('Keyword', back_populates='rule', cascade="all, delete-orphan")
    replace_rules = relationship('ReplaceRule', back_populates='rule', cascade="all, delete-orphan")
    media_types = relationship('MediaTypes', uselist=False, back_populates='rule', cascade="all, delete-orphan")
    media_extensions = relationship('MediaExtensions', back_populates='rule', cascade="all, delete-orphan")
    rss_config = relationship('RSSConfig', uselist=False, back_populates='rule', cascade="all, delete-orphan")
    rule_syncs = relationship('RuleSync', back_populates='rule', cascade="all, delete-orphan")
    push_config = relationship('PushConfig', uselist=False, back_populates='rule', cascade="all, delete-orphan")
    # 新增关系
    rule_logs = relationship('RuleLog', back_populates='rule', cascade="all, delete-orphan")
    rule_statistics = relationship('RuleStatistics', back_populates='rule', cascade="all, delete-orphan")

class ForwardMapping(Base):
    """多对多转发表：允许一个源会话映射到多个目标会话，并可选择性绑定具体规则"""
    __tablename__ = 'forward_mappings'

    id = Column(Integer, primary_key=True)
    source_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False, index=True)
    target_chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=True, index=True)
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    __table_args__ = (
        UniqueConstraint('source_chat_id', 'target_chat_id', 'rule_id', name='unique_source_target_rule'),
    )

    # 关系
    source_chat = relationship('Chat', foreign_keys=[source_chat_id])
    target_chat = relationship('Chat', foreign_keys=[target_chat_id])
    rule = relationship('ForwardRule')

class Keyword(Base):
    __tablename__ = 'keywords'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    keyword = Column(String, nullable=True)
    is_regex = Column(Boolean, default=False)
    is_blacklist = Column(Boolean, default=True)

    # 关系
    rule = relationship('ForwardRule', back_populates='keywords')

    # 添加唯一约束
    __table_args__ = (
        UniqueConstraint('rule_id', 'keyword','is_regex','is_blacklist', name='unique_rule_keyword_is_regex_is_blacklist'),
    )

class ReplaceRule(Base):
    __tablename__ = 'replace_rules'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    pattern = Column(String, nullable=False)  # 替换模式
    content = Column(String, nullable=True)   # 替换内容

    # 关系
    rule = relationship('ForwardRule', back_populates='replace_rules')

    # 添加唯一约束
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

    # 关系
    rule = relationship('ForwardRule', back_populates='media_types')


class MediaExtensions(Base):
    __tablename__ = 'media_extensions'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    extension = Column(String, nullable=False)  # 存储不带点的扩展名，如 "jpg", "pdf"

    # 关系
    rule = relationship('ForwardRule', back_populates='media_extensions')

    # 添加唯一约束
    __table_args__ = (
        UniqueConstraint('rule_id', 'extension', name='unique_rule_extension'),
    )

class RuleSync(Base):
    __tablename__ = 'rule_syncs'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    sync_rule_id = Column(Integer, nullable=False)

    # 关系
    rule = relationship('ForwardRule', back_populates='rule_syncs')

class PushConfig(Base):
    __tablename__ = 'push_configs'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False)
    enable_push_channel = Column(Boolean, default=False)
    push_channel = Column(String, nullable=False)
    #媒体发送方式，一次一张Single还是多张Multiple
    media_send_mode = Column(String, nullable=False, default='Single')

    # 关系
    rule = relationship('ForwardRule', back_populates='push_config')

class RSSConfig(Base):
    __tablename__ = 'rss_configs'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, unique=True)
    enable_rss = Column(Boolean, default=False)  # 是否启用RSS
    rule_title = Column(String, nullable=True)  # RSS feed 标题
    rule_description = Column(String, nullable=True)  # RSS feed 描述
    language = Column(String, default='zh-CN')  # RSS feed 语言
    max_items = Column(Integer, default=50)  # RSS feed 最大条目数
    # 是否启用自动提取标题和内容
    is_auto_title = Column(Boolean, default=False)
    is_auto_content = Column(Boolean, default=False)
    # 是否启用ai提取标题和内容
    is_ai_extract = Column(Boolean, default=False)
    # ai提取标题和内容的prompt
    ai_extract_prompt = Column(String, nullable=True)
    is_auto_markdown_to_html = Column(Boolean, default=False)
    # 压缩标志
    is_description_compressed = Column(Boolean, default=False)  # rule_description 是否压缩
    is_prompt_compressed = Column(Boolean, default=False)  # ai_extract_prompt 是否压缩
    # 是否启用自定义提取标题和内容的正则表达式
    enable_custom_title_pattern = Column(Boolean, default=False)
    enable_custom_content_pattern = Column(Boolean, default=False)

    # 关系
    rule = relationship('ForwardRule', back_populates='rss_config')
    patterns = relationship('RSSPattern', back_populates='rss_config', cascade="all, delete-orphan")


class RSSPattern(Base):
    __tablename__ = 'rss_patterns'


    id = Column(Integer, primary_key=True)
    rss_config_id = Column(Integer, ForeignKey('rss_configs.id'), nullable=False)
    pattern = Column(String, nullable=False)  # 正则表达式模式
    pattern_type = Column(String, nullable=False)  # 模式类型: 'title' 或 'content'
    priority = Column(Integer, default=0)  # 执行优先级,数字越小优先级越高


    # 关系
    rss_config = relationship('RSSConfig', back_populates='patterns')

    # 添加联合唯一约束
    __table_args__ = (
        UniqueConstraint('rss_config_id', 'pattern', 'pattern_type', name='unique_rss_pattern'),
    )

class MediaSignature(Base):
    __tablename__ = 'media_signatures'

    id = Column(Integer, primary_key=True)
    chat_id = Column(String, nullable=False, index=True)  # 目标聊天的 telegram_chat_id（字符串形式，保持与Chat表一致）
    signature = Column(String, nullable=False, index=True)  # 媒体唯一签名，如 photo:123456789 或 document:987654321
    # 新增：更精确的持久化字段
    file_id = Column(String, nullable=True, index=True)  # Telegram 文件ID/文档ID（用于视频/文档）
    content_hash = Column(String, nullable=True, index=True)  # 内容哈希（如视频部分字节hash、文本hash）
    message_id = Column(Integer, nullable=True)  # 可选：记录对应消息ID
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    # 出现次数：用于扫描重复（保持唯一键不变，重复时递增计数）
    count = Column(Integer, default=1)
    # 新增字段
    media_type = Column(String, nullable=True)  # 媒体类型：photo, video, document
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    file_name = Column(String, nullable=True)  # 文件名
    mime_type = Column(String, nullable=True)  # MIME类型
    duration = Column(Integer, nullable=True)  # 持续时间（视频/音频）
    width = Column(Integer, nullable=True)  # 宽度
    height = Column(Integer, nullable=True)  # 高度
    last_seen = Column(String, nullable=True)  # 最后出现时间

    __table_args__ = (
        UniqueConstraint('chat_id', 'signature', name='unique_chat_signature'),
    )

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True, index=True)  
    password = Column(String, nullable=False)
    # 新增字段
    email = Column(String, nullable=True)
    telegram_id = Column(String, nullable=True, unique=True, index=True)  # Telegram ID
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    last_login = Column(String, nullable=True)
    login_count = Column(Integer, default=0)
    # 2FA 字段
    totp_secret = Column(String, nullable=True)  # TOTP 密钥
    is_2fa_enabled = Column(Boolean, default=False)  # 是否启用 2FA
    backup_codes = Column(String, nullable=True)  # 备份码 (JSON)
    last_otp_token = Column(String, nullable=True) # 最后使用的 OTP 验证码 (防止重放)
    last_otp_at = Column(String, nullable=True) # 最后验证时间

class ChatStatistics(Base):
    """聊天统计表"""
    __tablename__ = 'chat_statistics'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False, index=True)
    date = Column(String, nullable=False, index=True)  # 日期 (YYYY-MM-DD)
    message_count = Column(Integer, default=0)  # 消息数量
    media_count = Column(Integer, default=0)  # 媒体数量
    user_count = Column(Integer, default=0)  # 活跃用户数
    forward_count = Column(Integer, default=0)  # 转发数量
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # 关系
    chat = relationship('Chat', back_populates='chat_stats')
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'date', name='unique_chat_date_stats'),
    )

class RuleStatistics(Base):
    """规则统计表"""
    __tablename__ = 'rule_statistics'
    
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, index=True)
    date = Column(String, nullable=False, index=True)  # 日期 (YYYY-MM-DD)
    processed_count = Column(Integer, default=0)  # 处理的消息数
    forwarded_count = Column(Integer, default=0)  # 成功转发数
    filtered_count = Column(Integer, default=0)  # 被过滤数
    error_count = Column(Integer, default=0)  # 错误数
    avg_processing_time = Column(Integer, default=0)  # 平均处理时间（毫秒）
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
    # 关系
    rule = relationship('ForwardRule', back_populates='rule_statistics')
    
    __table_args__ = (
        UniqueConstraint('rule_id', 'date', name='unique_rule_date_stats'),
    )

class RuleLog(Base):
    """规则操作日志表"""
    __tablename__ = 'rule_logs'
    
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)  # 操作类型：forward, filter, error
    source_message_id = Column(Integer, nullable=True)  # 源消息ID
    target_message_id = Column(Integer, nullable=True)  # 目标消息ID
    result = Column(String, nullable=True)  # 操作结果
    error_message = Column(String, nullable=True)  # 错误信息
    processing_time = Column(Integer, nullable=True)  # 处理时间（毫秒）
    is_result_compressed = Column(Boolean, default=False)  # result 是否压缩
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat(), index=True)
    
    # 关系
    rule = relationship('ForwardRule', back_populates='rule_logs')

class SystemConfiguration(Base):
    """系统配置表"""
    __tablename__ = 'system_configurations'
    
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(String, nullable=True)
    data_type = Column(String, default='string')  # string, integer, boolean, json
    description = Column(String, nullable=True)
    is_encrypted = Column(Boolean, default=False)  # 是否加密存储
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())

class ErrorLog(Base):
    """错误日志表"""
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    level = Column(String, nullable=False, index=True)  # ERROR, WARNING, CRITICAL
    module = Column(String, nullable=True, index=True)  # 模块名
    function = Column(String, nullable=True)  # 函数名
    message = Column(String, nullable=False)  # 错误信息
    traceback = Column(String, nullable=True)  # 堆栈跟踪
    context = Column(String, nullable=True)  # 上下文信息（JSON）
    user_id = Column(String, nullable=True)  # 用户ID
    is_traceback_compressed = Column(Boolean, default=False)  # traceback 是否压缩
    rule_id = Column(Integer, nullable=True)  # 相关规则ID
    chat_id = Column(String, nullable=True)  # 相关聊天ID
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat(), index=True)

class TaskQueue(Base):
    """任务队列表"""
    __tablename__ = 'task_queue'
    
    id = Column(Integer, primary_key=True)
    task_type = Column(String, nullable=False, index=True)  # 任务类型
    task_data = Column(String, nullable=True)  # 任务数据（JSON）
    status = Column(String, default='pending', index=True)  # pending, running, completed, failed
    priority = Column(Integer, default=0, index=True)  # 优先级
    retry_count = Column(Integer, default=0)  # 重试次数
    max_retries = Column(Integer, default=3)  # 最大重试次数
    scheduled_at = Column(DateTime, nullable=True, index=True)  # 计划执行时间
    started_at = Column(DateTime, nullable=True)  # 开始时间
    completed_at = Column(DateTime, nullable=True)  # 完成时间
    error_message = Column(String, nullable=True)  # 错误信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # [新增] 方案七核心字段：下次重试时间
    next_retry_at = Column(DateTime, nullable=True, index=True)
    # [新增] 统一错误日志字段
    error_log = Column(Text, nullable=True)
    # 优化：将高频统计字段提升为独立列，减少 JSON 解析与加速列表/详情查询
    done_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    forwarded_count = Column(Integer, default=0)
    filtered_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    last_message_id = Column(Integer, nullable=True)
    source_chat_id = Column(String, nullable=True)
    target_chat_id = Column(String, nullable=True)
    # [Scheme 7 Standard] 业务唯一键 (Business Key)
    # 用于防止重复生产任务
    unique_key = Column(String, unique=True, index=True, nullable=True) 
    # [Scheme 7 Standard] 媒体组ID (Media Group ID)
    # 用于聚合多张图片/视频为单个任务
    grouped_id = Column(String, index=True, nullable=True)


    # 示例值: "tg:-100123456:108"

class AuditLog(Base):
    """
    审计日志表
    用于记录所有安全相关操作（登录、登出、敏感数据修改等）
    P0 Security Requirement
    """
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    username = Column(String, nullable=True)  # 冗余字段，便于查询和历史回溯
    action = Column(String, nullable=False, index=True)  # 操作类型: LOGIN, LOGOUT, CREATE_RULE, etc.
    resource_type = Column(String, nullable=True)  # 资源类型: USER, RULE, SYSTEM
    resource_id = Column(String, nullable=True)  # 资源ID
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    details = Column(String, nullable=True)  # 详情 (JSON格式)
    status = Column(String, default='success')  # success / failure
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # 关系
    user = relationship('User', backref='audit_logs')

class ActiveSession(Base):
    """
    活跃会话表 (Active Sessions)
    用于管理用户登录会话，支持 Token 刷新和强制下线
    Phase 2 Security Requirement
    """
    __tablename__ = 'active_sessions'

    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, index=True, nullable=False) # 唯一会话ID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    device_info = Column(String, nullable=True) # 简化的设备信息
    refresh_token_hash = Column(String, nullable=False) # 刷新令牌的哈希值
    is_active = Column(Boolean, default=True) # 是否有效
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow) # 最后活跃时间

    user = relationship('User', backref='sessions')

class RSSSubscription(Base):
    """
    外部 RSS 订阅表 (External RSS Subscriptions)
    用于 Bot 主动从外部读取 RSS 并转发到指定群组
    [AIMD Implementation Target]
    """
    __tablename__ = 'rss_subscriptions'

    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, index=True)
    target_chat_id = Column(String, nullable=False, index=True) # 目标频道/群组 ID
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=True) # 关联规则
    
    # 状态字段
    is_active = Column(Boolean, default=True)
    last_checked = Column(String, nullable=True) # ISO Time
    last_etag = Column(String, nullable=True)
    last_modified = Column(String, nullable=True)
    latest_post_date = Column(DateTime, nullable=True) # 上次抓取的最新文章发布时间
    fail_count = Column(Integer, default=0) # 连续失败次数
    
    # AIMD 变量
    min_interval = Column(Integer, default=60)    # 最小 1 分钟
    max_interval = Column(Integer, default=3600)  # 最大 1 小时
    current_interval = Column(Integer, default=600) # 当前 10 分钟
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AccessControlList(Base):
    """
    IP 访问控制列表 (ACL)
    用于管理允许/禁止访问 Admin API 的 IP
    Phase 3 Security Requirement
    """
    __tablename__ = 'access_control_list'

    id = Column(Integer, primary_key=True)
    ip_address = Column(String(45), nullable=False, index=True) # IPv4 or IPv6
    type = Column(String(10), nullable=False) # ALLOW or BLOCK
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('ip_address', 'type', name='unique_ip_type'),
    )

def migrate_db(engine):
    """数据库迁移函数，确保新字段的添加"""
    inspector = inspect(engine)
    
    # 获取当前数据库中所有表
    existing_tables = inspector.get_table_names()
    
    # 连接数据库
    try:
        connection = engine.connect()
    except Exception as e:
        logger.error(f"无法连接到数据库进行迁移: {e}")
        return

    # 分步骤执行迁移，避免一个错误导致全部失败
    
    # 1. 创建缺失的表
    try:
        with engine.connect() as connection:

            # 如果chats表不存在，创建表
            if 'chats' not in existing_tables:
                logger.info("创建chats表...")
                Chat.__table__.create(engine)

            # 如果forward_rules表不存在，创建表
            if 'forward_rules' not in existing_tables:
                logger.info("创建forward_rules表...")
                ForwardRule.__table__.create(engine)

            # 如果keywords表不存在，创建表
            if 'keywords' not in existing_tables:
                logger.info("创建keywords表...")
                Keyword.__table__.create(engine)
            
            # 如果replace_rules表不存在，创建表
            if 'replace_rules' not in existing_tables:
                logger.info("创建replace_rules表...")
                ReplaceRule.__table__.create(engine)

            # 如果rule_syncs表不存在，创建表
            if 'rule_syncs' not in existing_tables:
                logger.info("创建rule_syncs表...")
                RuleSync.__table__.create(engine)


            # 如果users表不存在，创建表
            if 'users' not in existing_tables:
                logger.info("创建users表...")
                User.__table__.create(engine)

            # 如果rss_configs表不存在，创建表
            if 'rss_configs' not in existing_tables:
                logger.info("创建rss_configs表...")
                RSSConfig.__table__.create(engine)
                

            # 如果rss_patterns表不存在，创建表
            if 'rss_patterns' not in existing_tables:
                logger.info("创建rss_patterns表...")
                RSSPattern.__table__.create(engine)

            if 'audit_logs' not in existing_tables:
                logger.info("创建audit_logs表...")
                AuditLog.__table__.create(engine, checkfirst=True)

            if 'active_sessions' not in existing_tables:
                logger.info("创建active_sessions表...")
                ActiveSession.__table__.create(engine)

            # 如果push_configs表不存在，创建表
            if 'push_configs' not in existing_tables:
                logger.info("创建push_configs表...")
                PushConfig.__table__.create(engine)
            # 如果media_signatures表不存在，创建表
            if 'media_signatures' not in existing_tables:
                logger.info("创建media_signatures表...")
                MediaSignature.__table__.create(engine)
                
            # 创建新的统计和管理表
            new_tables = {
                'chat_statistics': ChatStatistics,
                'rule_statistics': RuleStatistics, 
                'rule_logs': RuleLog,
                'system_configurations': SystemConfiguration,
                'error_logs': ErrorLog,
                'task_queue': TaskQueue,
                # 'audit_logs': AuditLog  # ✅ 已在上方单独处理，避免重复创建
            }
            for table_name, table_class in new_tables.items():
                if table_name not in existing_tables:
                    logger.info(f"创建{table_name}表...")
                    table_class.__table__.create(engine, checkfirst=True)

            # 如果forward_mappings表不存在，创建表
            if 'forward_mappings' not in existing_tables:
                logger.info("创建forward_mappings表...")
                ForwardMapping.__table__.create(engine)

            # 如果rss_subscriptions表不存在，创建表
            if 'rss_subscriptions' not in existing_tables:
                logger.info("创建rss_subscriptions表...")
                RSSSubscription.__table__.create(engine)

            # 创建ACL表
            if 'access_control_list' not in existing_tables:
                logger.info("创建access_control_list表...")
                AccessControlList.__table__.create(engine)
            
            # 补充现有表的新字段
            try:
                # media_signatures 新字段
                new_columns = [
                    'ALTER TABLE media_signatures ADD COLUMN count INTEGER DEFAULT 1',
                    'ALTER TABLE media_signatures ADD COLUMN media_type VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN file_size INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN file_name VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN mime_type VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN duration INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN width INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN height INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN last_seen VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN updated_at VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN file_id VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN content_hash VARCHAR'
                ]
                
                for sql in new_columns:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass  # 字段已存在
                        
                logger.info('已更新 media_signatures 表结构')
            except Exception as e:
                logger.warning(f'更新 media_signatures 表失败: {str(e)}')
            
            # 为新旧表添加字段
            try:
                # Chat 表新字段
                chat_columns = [
                    'ALTER TABLE chats ADD COLUMN chat_type VARCHAR',
                    'ALTER TABLE chats ADD COLUMN username VARCHAR',
                    'ALTER TABLE chats ADD COLUMN created_at VARCHAR',
                    'ALTER TABLE chats ADD COLUMN updated_at VARCHAR', 
                    'ALTER TABLE chats ADD COLUMN is_active BOOLEAN DEFAULT 1',
                    'ALTER TABLE chats ADD COLUMN member_count INTEGER',
                    'ALTER TABLE chats ADD COLUMN description VARCHAR'
                ]
                
                # ForwardRule 表新字段
                rule_columns = [
                    'ALTER TABLE forward_rules ADD COLUMN created_at VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN updated_at VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN created_by VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN priority INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN description VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN message_count INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN last_used VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN daily_limit INTEGER',
                    'ALTER TABLE forward_rules ADD COLUMN rate_limit INTEGER',
                    'ALTER TABLE forward_rules ADD COLUMN webhook_url VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN custom_config VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN allow_delete_source_on_dedup BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN message_thread_id INTEGER',  # 新增: 话题组ID支持
                    # 精确媒体筛选字段
                    'ALTER TABLE forward_rules ADD COLUMN enable_duration_filter BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_duration INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_duration INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN enable_resolution_filter BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_width INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_width INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_height INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_height INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN enable_file_size_range BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_file_size INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_file_size INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN is_save_to_local BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN unique_key VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN grouped_id VARCHAR'
                ]
                
                # User 表新字段
                user_columns = [
                    'ALTER TABLE users ADD COLUMN email VARCHAR',
                    'ALTER TABLE users ADD COLUMN telegram_id VARCHAR',
                    'ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1',
                    'ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0',
                    'ALTER TABLE users ADD COLUMN created_at VARCHAR',
                    'ALTER TABLE users ADD COLUMN last_login VARCHAR',
                    'ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0',
                    # 2FA Fields
                    'ALTER TABLE users ADD COLUMN totp_secret VARCHAR',
                    'ALTER TABLE users ADD COLUMN is_2fa_enabled BOOLEAN DEFAULT 0',
                    'ALTER TABLE users ADD COLUMN backup_codes VARCHAR',
                    'ALTER TABLE users ADD COLUMN last_otp_token VARCHAR',
                    'ALTER TABLE users ADD COLUMN last_otp_at VARCHAR'
                ]
                
                all_columns = chat_columns + rule_columns + user_columns
                for sql in all_columns:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass  # 字段已存在

                        
                # TaskQueue 表新增统计与辅助列
                taskqueue_new_columns = [
                    'ALTER TABLE task_queue ADD COLUMN done_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN total_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN forwarded_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN filtered_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN failed_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN last_message_id INTEGER',
                    'ALTER TABLE task_queue ADD COLUMN source_chat_id VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN target_chat_id VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN unique_key VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN grouped_id VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN next_retry_at TIMESTAMP',
                    'ALTER TABLE task_queue ADD COLUMN error_log TEXT',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_unique_key ON task_queue(unique_key)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_grouped_id ON task_queue(grouped_id)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_next_retry ON task_queue(next_retry_at)'
                ]
                for sql in taskqueue_new_columns:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass

                logger.info('已更新所有表的新字段')
            except Exception as e:
                logger.warning(f'更新表字段失败: {str(e)}')
                
            # 添加性能优化索引（原有 + 新增）
            try:
                indexes = [
                    # 原有索引
                    'CREATE INDEX IF NOT EXISTS idx_media_signatures_chat_signature ON media_signatures(chat_id, signature)',
                    'CREATE INDEX IF NOT EXISTS idx_media_signatures_chat_count ON media_signatures(chat_id, count)',
                    'CREATE INDEX IF NOT EXISTS idx_forward_rules_source_enabled ON forward_rules(source_chat_id, enable_rule)',
                    'CREATE INDEX IF NOT EXISTS idx_forward_rules_target ON forward_rules(target_chat_id)',
                    'CREATE INDEX IF NOT EXISTS idx_keywords_rule_type ON keywords(rule_id, is_regex, is_blacklist)',
                    'CREATE INDEX IF NOT EXISTS idx_rss_configs_rule_enabled ON rss_configs(rule_id, enable_rss)',
                    'CREATE INDEX IF NOT EXISTS idx_push_configs_rule_enabled ON push_configs(rule_id, enable_push_channel)',
                    'CREATE INDEX IF NOT EXISTS idx_replace_rules_rule ON replace_rules(rule_id)',
                    
                    # 新增索引
                    'CREATE INDEX IF NOT EXISTS idx_chats_type_active ON chats(chat_type, is_active)',
                    'CREATE INDEX IF NOT EXISTS idx_forward_rules_priority ON forward_rules(priority DESC)',
                    'CREATE INDEX IF NOT EXISTS idx_forward_rules_created_at ON forward_rules(created_at)',
                    'CREATE INDEX IF NOT EXISTS idx_media_signatures_type_size ON media_signatures(media_type, file_size)',
                    'CREATE INDEX IF NOT EXISTS idx_media_signatures_last_seen ON media_signatures(last_seen)',
                    'CREATE INDEX IF NOT EXISTS idx_rule_logs_action_created ON rule_logs(action, created_at)',
                    'CREATE INDEX IF NOT EXISTS idx_rule_logs_rule_created ON rule_logs(rule_id, created_at)',
                    'CREATE INDEX IF NOT EXISTS idx_rule_statistics_date ON rule_statistics(date)',
                    'CREATE INDEX IF NOT EXISTS idx_chat_statistics_date ON chat_statistics(date)',
                    'CREATE INDEX IF NOT EXISTS idx_error_logs_level_created ON error_logs(level, created_at)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_status_priority ON task_queue(status, priority DESC)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_scheduled ON task_queue(scheduled_at)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_type_status ON task_queue(task_type, status)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_type_id_desc ON task_queue(task_type, id DESC)',
                    'CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_configurations(key)'
                ]
                
                for sql in indexes:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass
                        
                logger.info('已创建所有性能优化索引')
            except Exception as e:
                logger.warning(f'创建索引时出错: {str(e)}')

   
                
            # 如果media_types表不存在，创建表
            if 'media_types' not in existing_tables:
                logger.info("创建media_types表...")
                MediaTypes.__table__.create(engine)
                
                # 检查forward_rules表的现有列
                forward_rules_columns = {column['name'] for column in inspector.get_columns('forward_rules')}
                
                # 如果forward_rules表中有selected_media_types列，迁移数据到新表
                if 'selected_media_types' in forward_rules_columns:
                    logger.info("迁移媒体类型数据到新表...")
                    # 查询所有规则
                    rules = connection.execute(text("SELECT id, selected_media_types FROM forward_rules WHERE selected_media_types IS NOT NULL"))
                    
                    for rule in rules:
                        rule_id = rule[0]
                        selected_types = rule[1]
                        if selected_types:
                            # 创建媒体类型记录
                            media_types_data = {
                                'photo': 'photo' in selected_types,
                                'document': 'document' in selected_types,
                                'video': 'video' in selected_types,
                                'audio': 'audio' in selected_types,
                                'voice': 'voice' in selected_types
                            }
                            
                            # 插入数据
                            connection.execute(
                                text("""
                                INSERT INTO media_types (rule_id, photo, document, video, audio, voice)
                                VALUES (:rule_id, :photo, :document, :video, :audio, :voice)
                                """),
                                {
                                    'rule_id': rule_id,
                                    'photo': media_types_data['photo'],
                                    'document': media_types_data['document'],
                                    'video': media_types_data['video'],
                                    'audio': media_types_data['audio'],
                                    'voice': media_types_data['voice']
                                }
                            )
            if 'media_extensions' not in existing_tables:
                logger.info("创建media_extensions表...")
                MediaExtensions.__table__.create(engine)
                
    except Exception as e:
        logger.error(f'创建基础表或迁移媒体数据时出错: {str(e)}')
    
    # 2. 检查并补充现有表的新字段
    try:
        with engine.connect() as connection:
            # 检查各表的现有列
            forward_rules_columns = {column['name'] for column in inspector.get_columns('forward_rules')}
            keyword_columns = {column['name'] for column in inspector.get_columns('keywords')}
            user_columns = {column['name'] for column in inspector.get_columns('users')}
            chat_columns = {column['name'] for column in inspector.get_columns('chats')}
            media_sigs_columns = {column['name'] for column in inspector.get_columns('media_signatures')}
            chat_columns = {column['name'] for column in inspector.get_columns('chats')}
            media_sigs_columns = {column['name'] for column in inspector.get_columns('media_signatures')}
            task_queue_columns = {column['name'] for column in inspector.get_columns('task_queue')}
            rss_sub_columns = {column['name'] for column in inspector.get_columns('rss_subscriptions')}
            rss_configs_columns = {column['name'] for column in inspector.get_columns('rss_configs')}
            rule_logs_columns = {column['name'] for column in inspector.get_columns('rule_logs')}
            error_logs_columns = {column['name'] for column in inspector.get_columns('error_logs')}

        # 需要添加的新列及其默认值
        forward_rules_new_columns = {
            'is_ai': 'ALTER TABLE forward_rules ADD COLUMN is_ai BOOLEAN DEFAULT FALSE',
            'ai_model': 'ALTER TABLE forward_rules ADD COLUMN ai_model VARCHAR DEFAULT NULL',
            'ai_prompt': 'ALTER TABLE forward_rules ADD COLUMN ai_prompt VARCHAR DEFAULT NULL',
            'is_summary': 'ALTER TABLE forward_rules ADD COLUMN is_summary BOOLEAN DEFAULT FALSE',
            'summary_time': 'ALTER TABLE forward_rules ADD COLUMN summary_time VARCHAR DEFAULT "07:00"',
            'summary_prompt': 'ALTER TABLE forward_rules ADD COLUMN summary_prompt VARCHAR DEFAULT NULL',
            'is_delete_original': 'ALTER TABLE forward_rules ADD COLUMN is_delete_original BOOLEAN DEFAULT FALSE',
            'is_original_sender': 'ALTER TABLE forward_rules ADD COLUMN is_original_sender BOOLEAN DEFAULT FALSE',
            'is_original_time': 'ALTER TABLE forward_rules ADD COLUMN is_original_time BOOLEAN DEFAULT FALSE',
            'is_keyword_after_ai': 'ALTER TABLE forward_rules ADD COLUMN is_keyword_after_ai BOOLEAN DEFAULT FALSE',
            'add_mode': 'ALTER TABLE forward_rules ADD COLUMN add_mode VARCHAR DEFAULT "BLACKLIST"',
            'enable_rule': 'ALTER TABLE forward_rules ADD COLUMN enable_rule BOOLEAN DEFAULT TRUE',
            'is_top_summary': 'ALTER TABLE forward_rules ADD COLUMN is_top_summary BOOLEAN DEFAULT TRUE',
            'is_filter_user_info': 'ALTER TABLE forward_rules ADD COLUMN is_filter_user_info BOOLEAN DEFAULT FALSE',
            'enable_delay': 'ALTER TABLE forward_rules ADD COLUMN enable_delay BOOLEAN DEFAULT FALSE',
            'delay_seconds': 'ALTER TABLE forward_rules ADD COLUMN delay_seconds INTEGER DEFAULT 5',
            'handle_mode': 'ALTER TABLE forward_rules ADD COLUMN handle_mode VARCHAR DEFAULT "FORWARD"',
            'enable_comment_button': 'ALTER TABLE forward_rules ADD COLUMN enable_comment_button BOOLEAN DEFAULT FALSE',
            'enable_media_type_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_media_type_filter BOOLEAN DEFAULT FALSE',
            'enable_media_size_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_media_size_filter BOOLEAN DEFAULT FALSE',
            'max_media_size': f'ALTER TABLE forward_rules ADD COLUMN max_media_size INTEGER DEFAULT {os.getenv("DEFAULT_MAX_MEDIA_SIZE", 10)}',
            'is_send_over_media_size_message': 'ALTER TABLE forward_rules ADD COLUMN is_send_over_media_size_message BOOLEAN DEFAULT TRUE',
            'enable_extension_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_extension_filter BOOLEAN DEFAULT FALSE',
            'extension_filter_mode': 'ALTER TABLE forward_rules ADD COLUMN extension_filter_mode VARCHAR DEFAULT "BLACKLIST"',
            'enable_reverse_blacklist': 'ALTER TABLE forward_rules ADD COLUMN enable_reverse_blacklist BOOLEAN DEFAULT FALSE',
            'enable_reverse_whitelist': 'ALTER TABLE forward_rules ADD COLUMN enable_reverse_whitelist BOOLEAN DEFAULT FALSE',
            'only_rss': 'ALTER TABLE forward_rules ADD COLUMN only_rss BOOLEAN DEFAULT FALSE',
            'enable_sync': 'ALTER TABLE forward_rules ADD COLUMN enable_sync BOOLEAN DEFAULT FALSE',
            'userinfo_template': 'ALTER TABLE forward_rules ADD COLUMN userinfo_template VARCHAR DEFAULT "**{name}**"',
            'time_template': 'ALTER TABLE forward_rules ADD COLUMN time_template VARCHAR DEFAULT "{time}"',
            'original_link_template': 'ALTER TABLE forward_rules ADD COLUMN original_link_template VARCHAR DEFAULT "原始连接：{original_link}"',
            'enable_push': 'ALTER TABLE forward_rules ADD COLUMN enable_push BOOLEAN DEFAULT FALSE',
            'enable_only_push': 'ALTER TABLE forward_rules ADD COLUMN enable_only_push BOOLEAN DEFAULT FALSE',
            'media_allow_text': 'ALTER TABLE forward_rules ADD COLUMN media_allow_text BOOLEAN DEFAULT FALSE',
            'enable_ai_upload_image': 'ALTER TABLE forward_rules ADD COLUMN enable_ai_upload_image BOOLEAN DEFAULT FALSE',
            'force_pure_forward': 'ALTER TABLE forward_rules ADD COLUMN force_pure_forward BOOLEAN DEFAULT FALSE',
            'enable_dedup': 'ALTER TABLE forward_rules ADD COLUMN enable_dedup BOOLEAN DEFAULT FALSE',
            'required_sender_id': 'ALTER TABLE forward_rules ADD COLUMN required_sender_id VARCHAR',
            'required_sender_regex': 'ALTER TABLE forward_rules ADD COLUMN required_sender_regex VARCHAR',
            'is_save_to_local': 'ALTER TABLE forward_rules ADD COLUMN is_save_to_local BOOLEAN DEFAULT FALSE',
        }

        keywords_new_columns = {
            'is_blacklist': 'ALTER TABLE keywords ADD COLUMN is_blacklist BOOLEAN DEFAULT TRUE',
        }

        rss_sub_new_columns = {
            'latest_post_date': 'ALTER TABLE rss_subscriptions ADD COLUMN latest_post_date TIMESTAMP',
            'fail_count': 'ALTER TABLE rss_subscriptions ADD COLUMN fail_count INTEGER DEFAULT 0',
        }

        rss_configs_new_columns = {
            'is_description_compressed': 'ALTER TABLE rss_configs ADD COLUMN is_description_compressed BOOLEAN DEFAULT 0',
            'is_prompt_compressed': 'ALTER TABLE rss_configs ADD COLUMN is_prompt_compressed BOOLEAN DEFAULT 0',
        }

        rule_logs_new_columns = {
            'is_result_compressed': 'ALTER TABLE rule_logs ADD COLUMN is_result_compressed BOOLEAN DEFAULT 0',
        }

        error_logs_new_columns = {
            'is_traceback_compressed': 'ALTER TABLE error_logs ADD COLUMN is_traceback_compressed BOOLEAN DEFAULT 0',
        }

        # 添加缺失的列
        with engine.connect() as connection:
            # 添加forward_rules表的列
            for column, sql in forward_rules_new_columns.items():
                if column not in forward_rules_columns:
                    try:
                        connection.execute(text(sql))
                        logger.info(f'已添加列: {column}')
                    except Exception as e:
                        logger.error(f'添加列 {column} 时出错: {str(e)}')
                        

            # 添加keywords表的列
            for column, sql in keywords_new_columns.items():
                if column not in keyword_columns:
                    try:
                        connection.execute(text(sql))
                        logger.info(f'已添加列: {column}')
                    except Exception as e:
                        logger.error(f'添加列 {column} 时出错: {str(e)}')

            # 添加rss_subscriptions表的列
            for column, sql in rss_sub_new_columns.items():
                if column not in rss_sub_columns:
                    try:
                        connection.execute(text(sql))
                        logger.info(f'已添加列: {column}')
                    except Exception as e:
                        logger.error(f'添加列 {column} 时出错: {str(e)}')

            # 添加rss_configs表的列
            for column, sql in rss_configs_new_columns.items():
                if column not in rss_configs_columns:
                    try:
                        connection.execute(text(sql))
                        logger.info(f'已添加列: {column}')
                    except Exception as e:
                        logger.error(f'添加列 {column} 时出错: {str(e)}')

            # 添加rule_logs表的列
            for column, sql in rule_logs_new_columns.items():
                if column not in rule_logs_columns:
                    try:
                        connection.execute(text(sql))
                        logger.info(f'已添加列: {column}')
                    except Exception as e:
                        logger.error(f'添加列 {column} 时出错: {str(e)}')

            # 添加error_logs表的列
            for column, sql in error_logs_new_columns.items():
                if column not in error_logs_columns:
                    try:
                        connection.execute(text(sql))
                        logger.info(f'已添加列: {column}')
                    except Exception as e:
                        logger.error(f'添加列 {column} 时出错: {str(e)}')

            #先检查forward_rules表的列的forward_mode是否存在
            if 'forward_mode' not in forward_rules_columns:
                # 修改forward_rules表的列mode为forward_mode
                connection.execute(text("ALTER TABLE forward_rules RENAME COLUMN mode TO forward_mode"))
                logger.info('修改forward_rules表的列mode为forward_mode成功')

            # 修改keywords表的唯一约束
            try:
                # 检查索引是否存在
                result = connection.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name='unique_rule_keyword_is_regex_is_blacklist'
                """))
                index_exists = result.fetchone() is not None
                if not index_exists:
                    logger.info('开始更新 keywords 表的唯一约束...')
                    try:
                        
                        with engine.begin() as connection:
                            # 创建临时表
                            connection.execute(text("""
                                CREATE TABLE keywords_temp (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    rule_id INTEGER,
                                    keyword TEXT,
                                    is_regex BOOLEAN,
                                    is_blacklist BOOLEAN
                                    -- 如果 keywords 表还有其他字段，请在这里一并定义
                                )
                            """))
                            logger.info('创建 keywords_temp 表结构成功')

                            # 将原表数据复制到临时表，让数据库自动生成 id
                            result = connection.execute(text("""
                                INSERT INTO keywords_temp (rule_id, keyword, is_regex, is_blacklist)
                                SELECT rule_id, keyword, is_regex, is_blacklist FROM keywords
                            """))
                            logger.info(f'复制数据到 keywords_temp 成功，影响行数: {result.rowcount}')

                            # 删除原表 keywords
                            connection.execute(text("DROP TABLE keywords"))
                            logger.info('删除原表 keywords 成功')

                            # 4将临时表重命名为 keywords
                            connection.execute(text("ALTER TABLE keywords_temp RENAME TO keywords"))
                            logger.info('重命名 keywords_temp 为 keywords 成功')

                            # 添加唯一约束
                            connection.execute(text("""
                                CREATE UNIQUE INDEX unique_rule_keyword_is_regex_is_blacklist 
                                ON keywords (rule_id, keyword, is_regex, is_blacklist)
                            """))
                            logger.info('添加唯一约束 unique_rule_keyword_is_regex_is_blacklist 成功')

                            logger.info('成功更新 keywords 表结构和唯一约束')
                    except Exception as e:
                        logger.error(f'更新 keywords 表结构时出错: {str(e)}')
                else:
                    logger.info('唯一约束已存在，跳过创建')

            except Exception as e:
                logger.error(f"更新唯一约束时出错: {e}")

    except Exception as e:
        logger.error(f"字段迁移或索引更新过程中出错: {e}")

# 全局引擎和会话工厂（单例模式）
_engine = None
_session_factory = None
_engine_lock = None

def get_engine():
    """获取全局数据库引擎（单例模式）。
    支持通过 `DATABASE_URL` 配置多种后端（SQLite/PostgreSQL/MySQL/TiDB/Cockroach）。
    当未设置时回退到本地 SQLite。
    """
    global _engine
    if _engine is None:
        # 连接配置
        database_url = settings.DATABASE_URL
        db_echo = settings.DB_ECHO
        pool_size = settings.DB_POOL_SIZE
        max_overflow = settings.DB_MAX_OVERFLOW
        pool_timeout = 30  # 默认值，可在settings中添加配置
        pool_recycle = 1800  # 默认值，可在settings中添加配置

        base_dir = Path(__file__).resolve().parent.parent
        if not database_url or database_url == "sqlite:///db/forward.db":
            db_path = (base_dir / 'db' / 'forward.db').resolve()
            os.makedirs(str(db_path.parent), exist_ok=True)
            database_url = f'sqlite:///{db_path}'
        else:
            _url_lc = database_url.lower()
            if _url_lc.startswith('sqlite') and ':memory:' not in _url_lc:
                prefix = 'sqlite:///'
                if database_url.startswith(prefix):
                    path_str = database_url[len(prefix):]
                    p = Path(path_str)
                    if not p.is_absolute():
                        abs_path = (base_dir / p).resolve()
                        os.makedirs(str(abs_path.parent), exist_ok=True)
                        database_url = f'sqlite:///{abs_path}'

        # 根据方言设置连接参数
        url_lc = database_url.lower()
        connect_args = {}
        engine_kwargs = {
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_timeout': pool_timeout,
            'pool_recycle': pool_recycle,
            'pool_pre_ping': True,
            'echo': db_echo,
        }

        if url_lc.startswith('sqlite'):
            # SQLite 专属优化
            connect_args = {
                'timeout': 60,  # 增加超时时间，等待锁释放
                'check_same_thread': False,
                'isolation_level': None, # 配合 WAL 模式手动管理事务
            }
            from sqlalchemy.pool import QueuePool
            _engine = create_engine(
                database_url,
                connect_args=connect_args,
                # ✅ 关键优化：显式使用 QueuePool 而非默认的 SingletonThreadPool
                poolclass=QueuePool, 
                pool_size=20,        # 增大连接池
                max_overflow=30,     # 允许溢出连接
                pool_timeout=60,
                pool_recycle=3600,   # 定期回收连接防止僵死
                pool_pre_ping=True,
                echo=engine_kwargs.get('echo', False),
            )

            # PRAGMA 优化
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                
                # 先检查数据库完整性
                try:
                    cursor.execute("PRAGMA integrity_check(1)")
                    result = cursor.fetchone()
                    if result[0] != "ok":
                        print(f"⚠️ 数据库完整性检查失败: {result[0]}")
                        print("🔧 建议运行修复脚本: python scripts/fix_database.py")
                        # 尝试快速修复
                        try:
                            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                            cursor.execute("VACUUM")
                        except Exception as vacuum_error:
                            print(f"⚠️ 自动修复失败: {vacuum_error}")
                except Exception as integrity_error:
                    print(f"❌ 数据库损坏严重: {integrity_error}")
                    print("🔧 请立即运行修复脚本: python scripts/fix_database.py")
                    raise
                
                # 设置优化参数
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA cache_size=10000")
                    cursor.execute("PRAGMA temp_store=MEMORY")
                    cursor.execute("PRAGMA mmap_size=268435456")
                    # 设置 busy_timeout 以在锁冲突时自动等待
                    cursor.execute("PRAGMA busy_timeout=30000")
                    # 启用外键约束，避免脏数据
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA optimize")
                except Exception as pragma_error:
                    print(f"⚠️ 设置数据库优化参数失败: {pragma_error}")
                    # 如果设置失败，尝试最基本的设置
                    try:
                        cursor.execute("PRAGMA journal_mode=DELETE")
                        cursor.execute("PRAGMA synchronous=FULL")
                    except Exception:
                        pass  # 忽略基本设置失败
                try:
                    limit_mb_env = os.getenv('DB_WAL_LIMIT_MB', '25')
                    limit_mb = int(limit_mb_env) if str(limit_mb_env).isdigit() else 25
                    if limit_mb < 1:
                        limit_mb = 25
                    page_size = 4096
                    try:
                        cursor.execute("PRAGMA page_size")
                        row = cursor.fetchone()
                        if row and isinstance(row[0], int) and row[0] > 0:
                            page_size = row[0]
                    except Exception:
                        pass
                    bytes_limit = limit_mb * 1024 * 1024
                    pages_threshold = max(100, int(bytes_limit // max(512, page_size)))
                    cursor.execute(f"PRAGMA wal_autocheckpoint={pages_threshold}")
                    cursor.execute(f"PRAGMA journal_size_limit={bytes_limit}")
                    try:
                        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
                except Exception:
                    pass
                finally:
                    try:
                        cursor.close()
                    except Exception:
                        pass
        else:
            # 非 SQLite：PostgreSQL / MySQL / TiDB / CockroachDB
            # 建议使用连接池与预检测以提升可用性
            # 允许通过环境变量控制 SSL/超时等（透传于 querystring）
            _engine = create_engine(database_url, **engine_kwargs)

        logger.info("数据库引擎初始化完成，已应用性能优化配置")

    return _engine

def get_session_factory():
    """获取全局会话工厂（单例模式）"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,  # 避免在事务提交后对象过期
            autoflush=True,          # 自动刷新更改
            autocommit=False         # 手动控制事务提交
        )
        logger.info("数据库会话工厂初始化完成")
    
    return _session_factory


# 读写分离（可选）：若提供 DATABASE_URL_READS，则使用只读引擎创建只读会话
_read_engine = None
_read_session_factory = None


def get_read_engine():
    """获取只读数据库引擎（如配置），否则回退到主引擎。"""
    global _read_engine
    if _read_engine is not None:
        return _read_engine
    read_url = os.getenv('DATABASE_URL_READS')
    base_dir = Path(__file__).resolve().parent.parent
    if not read_url:
        return get_engine()
    else:
        _url_lc = read_url.lower()
        if _url_lc.startswith('sqlite') and ':memory:' not in _url_lc:
            prefix = 'sqlite:///'
            if read_url.startswith(prefix):
                path_str = read_url[len(prefix):]
                p = Path(path_str)
                if not p.is_absolute():
                    abs_path = (base_dir / p).resolve()
                    os.makedirs(str(abs_path.parent), exist_ok=True)
                    read_url = f'sqlite:///{abs_path}'
    db_echo = os.getenv('DB_ECHO', 'false').lower() in ('1', 'true', 'yes')
    pool_size = int(os.getenv('DB_POOL_SIZE_READS', os.getenv('DB_POOL_SIZE', '50')))
    max_overflow = int(os.getenv('DB_MAX_OVERFLOW_READS', os.getenv('DB_MAX_OVERFLOW', '100')))
    pool_timeout = int(os.getenv('DB_POOL_TIMEOUT_READS', os.getenv('DB_POOL_TIMEOUT', '30')))
    pool_recycle = int(os.getenv('DB_POOL_RECYCLE_READS', os.getenv('DB_POOL_RECYCLE', '1800')))
    engine_kwargs = {
        'pool_size': pool_size,
        'max_overflow': max_overflow,
        'pool_timeout': pool_timeout,
        'pool_recycle': pool_recycle,
        'pool_pre_ping': True,
        'echo': db_echo,
    }
    try:
        _read_engine = create_engine(read_url, **engine_kwargs)
        logger.info("只读数据库引擎初始化完成")
    except Exception as e:
        logger.warning(f"只读数据库引擎初始化失败，回退到主引擎: {e}")
        _read_engine = get_engine()
    return _read_engine


def get_read_session_factory():
    """获取只读会话工厂（如未配置只读引擎则回退主库）。"""
    global _read_session_factory
    if _read_session_factory is None:
        _read_session_factory = sessionmaker(
            bind=get_read_engine(),
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )
    return _read_session_factory

# 去重分库引擎与会话
_dedup_engine = None
_dedup_session_factory = None

def get_dedup_engine():
    global _dedup_engine
    if _dedup_engine is not None:
        return _dedup_engine
    dedup_url = os.getenv('DEDUP_DATABASE_URL')
    if not dedup_url:
        _dedup_engine = get_engine()
        return _dedup_engine
    db_echo = os.getenv('DB_ECHO', 'false').lower() in ('1', 'true', 'yes')
    pool_size = int(os.getenv('DB_POOL_SIZE', '50'))
    max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '100'))
    pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '1800'))
    engine_kwargs = {
        'pool_size': pool_size,
        'max_overflow': max_overflow,
        'pool_timeout': pool_timeout,
        'pool_recycle': pool_recycle,
        'pool_pre_ping': True,
        'echo': db_echo,
    }
    try:
        url_lc = dedup_url.lower()
        if url_lc.startswith('sqlite'):
            _dedup_engine = create_engine(
                dedup_url,
                connect_args={'timeout': 30, 'check_same_thread': False, 'isolation_level': None},
                pool_size=engine_kwargs.get('pool_size', 10),
                max_overflow=engine_kwargs.get('max_overflow', 20),
                pool_timeout=engine_kwargs.get('pool_timeout', 30),
                pool_recycle=engine_kwargs.get('pool_recycle', 1800),
                pool_pre_ping=True,
                echo=engine_kwargs.get('echo', False),
            )
        else:
            _dedup_engine = create_engine(dedup_url, **engine_kwargs)
        logger.info("去重分库引擎初始化完成")
    except Exception as e:
        logger.warning(f"去重分库引擎初始化失败，回退主引擎: {e}")
        _dedup_engine = get_engine()
    return _dedup_engine

def get_dedup_session_factory():
    global _dedup_session_factory
    if _dedup_session_factory is None:
        _dedup_session_factory = sessionmaker(
            bind=get_dedup_engine(),
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )
    return _dedup_session_factory

def get_dedup_session():
    Session = get_dedup_session_factory()
    return Session()

def get_session():
    """创建数据库会话（优化版）"""
    Session = get_session_factory()
    return Session()


def get_read_session():
    """创建只读数据库会话（如未配置则返回主会话）。"""
    Session = get_read_session_factory()
    return Session()

def get_db_health():
    """检查数据库健康状态"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1')).fetchone()
            return {"status": "healthy", "connected": True, "result": result[0] if result else None}
    except Exception as e:
        logger.error(f"数据库健康检查失败: {str(e)}")
        return {"status": "unhealthy", "connected": False, "error": str(e)}


async def async_get_db_health():
    """异步检查数据库健康状态"""
    try:
        async_engine = get_async_engine()
        async with async_engine.connect() as conn:
            result = await conn.execute(text('SELECT 1'))
            result = await result.fetchone()
            return {"status": "healthy", "connected": True, "result": result[0] if result else None}
    except Exception as e:
        logger.error(f"异步数据库健康检查失败: {str(e)}")
        return {"status": "unhealthy", "connected": False, "error": str(e)}

class SessionManager:
    """数据库会话上下文管理器"""
    
    def __init__(self):
        self.session = None
    
    def __enter__(self):
        self.session = get_session()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            try:
                if exc_type is None:
                    self.session.commit()
                else:
                    self.session.rollback()
                    logger.error(f"会话回滚: {exc_type.__name__}: {exc_val}")
            except Exception as e:
                logger.error(f"会话管理器异常: {str(e)}")
                self.session.rollback()
            finally:
                self.session.close()
        return False  # 不抑制异常

# 便利函数：自动管理会话


# === 异步数据库支持 ===
# 全局异步引擎和会话工厂
_async_engine = None
_async_session_factory = None

from sqlalchemy.engine import Engine
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """开启 SQLite WAL 模式以支持高并发读写"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    finally:
        cursor.close()


def get_async_engine():
    """获取全局异步数据库引擎 (单例)"""
    global _async_engine
    if _async_engine is not None:
        return _async_engine

    # 获取配置
    database_url = os.getenv('DATABASE_URL')
    db_echo = os.getenv('DB_ECHO', 'false').lower() in ('1', 'true', 'yes')
    
    # 构造异步 URL
    base_dir = Path(__file__).resolve().parent.parent
    if not database_url:
        db_path = (base_dir / 'db' / 'forward.db').resolve()
        os.makedirs(str(db_path.parent), exist_ok=True)
        # 注意这里使用 +aiosqlite
        database_url = f'sqlite+aiosqlite:///{db_path}'
    else:
        # 自动转换同步 URL 为异步 URL
        if database_url.startswith('sqlite://') and 'aiosqlite' not in database_url:
             database_url = database_url.replace('sqlite://', 'sqlite+aiosqlite://')
        elif database_url.startswith('postgresql://'):
             database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')

    connect_args = {}
    if 'sqlite' in database_url:
        connect_args = {
            'timeout': 60,  # 增加超时时间，等待锁释放
            'check_same_thread': False,
            'isolation_level': None, # 配合 WAL 模式手动管理事务
        }

    # 从环境变量读取连接池配置 (Phase H.1)
    pool_size = int(os.environ.get('DB_POOL_SIZE', 20))
    max_overflow = int(os.environ.get('DB_MAX_OVERFLOW', 30))
    pool_timeout = int(os.environ.get('DB_POOL_TIMEOUT', 60))
    pool_recycle = int(os.environ.get('DB_POOL_RECYCLE', 3600))
    
    # SQLite 使用 QueuePool 以支持连接池参数
    engine_kwargs = {
        "echo": db_echo,
        "connect_args": connect_args,
        "pool_pre_ping": True,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_recycle": pool_recycle,
    }
    
    # SQLAlchemy 2.0 create_async_engine handles the pool class automatically.
    # Specifying QueuePool (sync) is incompatible with asyncio.
    # if 'sqlite' in database_url:
    #     engine_kwargs['poolclass'] = QueuePool
    if 'sqlite' in database_url:
        # SQLite doesn't support pool_size, max_overflow (especially with StaticPool for memory DB)
        engine_kwargs.pop('pool_size', None)
        engine_kwargs.pop('max_overflow', None)
        engine_kwargs.pop('pool_timeout', None)
    else:
        logger.info(f"数据库连接池配置: pool_size={pool_size}, max_overflow={max_overflow}")
    
    _async_engine = create_async_engine(
        database_url,
        **engine_kwargs
    )
    logger.info(f"异步数据库引擎初始化完成: {database_url}")
    return _async_engine


def get_async_session_factory():
    """获取异步会话工厂"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
            class_=AsyncSession
        )
    return _async_session_factory


class AsyncSessionManager:
    """异步数据库会话上下文管理器"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        factory = get_async_session_factory()
        self.session = factory()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
        except Exception as e:
            # 确保在提交失败时也能正确回滚
            try:
                await self.session.rollback()
            except Exception:
                pass
            raise e
        finally:
            # 确保无论如何都会关闭会话
            await self.session.close()


def get_async_session():
    """返回一个 AsyncSession 实例，调用者需要自行关闭或使用 async with"""
    factory = get_async_session_factory()
    return factory()
def with_session(func):
    """装饰器：自动管理数据库会话"""
    # 根据函数类型选择使用同步还是异步会话管理
    import inspect
    if inspect.iscoroutinefunction(func):
        # 异步函数使用异步会话管理器
        async def wrapper(*args, **kwargs):
            async with AsyncSessionManager() as session:
                return await func(session, *args, **kwargs)
    else:
        # 同步函数使用同步会话管理器
        def wrapper(*args, **kwargs):
            with SessionManager() as session:
                return func(session, *args, **kwargs)
    return wrapper

# 数据库维护工具
def backup_database(backup_path=None):
    """备份数据库"""
    import shutil
    from datetime import datetime
    
    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = Path(__file__).resolve().parent.parent
        backup_path = str((base_dir / 'db' / 'backup' / f"forward_backup_{timestamp}.db").resolve())
    
    # 确保备份目录存在
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    
    try:
        # 使用 SQLite 备份 API
        base_dir = Path(__file__).resolve().parent.parent
        source_db = (base_dir / 'db' / 'forward.db').resolve()
        if source_db.exists():
            shutil.copy2(str(source_db), backup_path)
            logger.info(f"数据库备份成功: {backup_path}")
            return backup_path
        else:
            logger.error("源数据库文件不存在")
            return None
    except Exception as e:
        logger.error(f"数据库备份失败: {str(e)}")
        return None

def vacuum_database():
    """清理数据库碎片"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            logger.info("数据库碎片清理完成")
            return True
    except Exception as e:
        logger.error(f"数据库碎片清理失败: {str(e)}")
        return False


async def async_vacuum_database():
    """异步清理数据库碎片"""
    try:
        async_engine = get_async_engine()
        async with async_engine.connect() as conn:
            await conn.execute(text("VACUUM"))
            logger.info("异步数据库碎片清理完成")
            return True
    except Exception as e:
        logger.error(f"异步数据库碎片清理失败: {str(e)}")
        return False

def analyze_database():
    """分析数据库统计信息"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("ANALYZE"))
            logger.info("数据库分析完成")
            return True
    except Exception as e:
        logger.error(f"数据库分析失败: {str(e)}")
        return False


async def async_analyze_database():
    """异步分析数据库统计信息"""
    try:
        async_engine = get_async_engine()
        async with async_engine.connect() as conn:
            await conn.execute(text("ANALYZE"))
            logger.info("异步数据库分析完成")
            return True
    except Exception as e:
        logger.error(f"异步数据库分析失败: {str(e)}")
        return False

def get_database_info():
    """获取数据库信息"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # 数据库大小
            size_result = conn.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")).fetchone()
            db_size = size_result[0] if size_result else 0
            
            # 表数量
            tables_result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")).fetchone()
            table_count = tables_result[0] if tables_result else 0
            
            # 索引数量
            indexes_result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")).fetchone()
            index_count = indexes_result[0] if indexes_result else 0
            
            return {
                'size': db_size,
                'tables': table_count,
                'indexes': index_count
            }
    except Exception as e:
        logger.error(f"获取数据库信息失败: {str(e)}")
        return {
            'size': 0,
            'tables': 0,
            'indexes': 0
        }

# ... (在 get_dedup_session_factory 函数之后，添加异步去重支持)

# 全局异步去重引擎和会话工厂
_async_dedup_engine = None
_async_dedup_session_factory = None

def get_async_dedup_engine():
    """获取全局异步去重数据库引擎"""
    global _async_dedup_engine
    if _async_dedup_engine is not None:
        return _async_dedup_engine

    dedup_url = os.getenv('DEDUP_DATABASE_URL')
    if not dedup_url:
        # 如果未配置去重库，复用主异步引擎
        _async_dedup_engine = get_async_engine()
        return _async_dedup_engine

    db_echo = os.getenv('DB_ECHO', 'false').lower() in ('1', 'true', 'yes')
    
    # 自动转换同步URL为异步URL
    if dedup_url.startswith('sqlite://') and 'aiosqlite' not in dedup_url:
         dedup_url = dedup_url.replace('sqlite://', 'sqlite+aiosqlite://')
    elif dedup_url.startswith('postgresql://'):
         dedup_url = dedup_url.replace('postgresql://', 'postgresql+asyncpg://')

    connect_args = {}
    if 'sqlite' in dedup_url:
        connect_args = {'timeout': 30}

    _async_dedup_engine = create_async_engine(
        dedup_url,
        echo=db_echo,
        connect_args=connect_args,
        pool_pre_ping=True
    )
    logger.info(f"异步去重数据库引擎初始化完成: {dedup_url}")
    return _async_dedup_engine

def get_async_dedup_session_factory():
    """获取异步去重会话工厂"""
    global _async_dedup_session_factory
    if _async_dedup_session_factory is None:
        _async_dedup_session_factory = async_sessionmaker(
            bind=get_async_dedup_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession
        )
    return _async_dedup_session_factory


async def async_get_database_info():
    """异步获取数据库信息"""
    try:
        async_engine = get_async_engine()
        async with async_engine.connect() as conn:
            # 数据库大小
            size_result = await conn.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"))
            size_result = await size_result.fetchone()
            db_size = size_result[0] if size_result else 0
            
            # 表数量
            tables_result = await conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            tables_result = await tables_result.fetchone()
            table_count = tables_result[0] if tables_result else 0
            
            # 索引数量
            indexes_result = await conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='index'"))
            indexes_result = await indexes_result.fetchone()
            index_count = indexes_result[0] if indexes_result else 0
            
            # WAL 文件大小
            wal_size = 0
            wal_file = (Path(__file__).resolve().parent.parent / 'db' / 'forward.db-wal').resolve()
            if wal_file.exists():
                wal_size = os.path.getsize(str(wal_file))
            
            return {
                "db_size": db_size,
                "wal_size": wal_size,
                "table_count": table_count,
                "index_count": index_count,
                "total_size": db_size + wal_size
            }
    except Exception as e:
        logger.error(f"异步获取数据库信息失败: {str(e)}")
        return None

def cleanup_old_logs(days=30):
    """清理旧日志"""
    try:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with SessionManager() as session:
            # 清理错误日志
            deleted_errors = session.query(ErrorLog).filter(ErrorLog.created_at < cutoff_date).delete()
            
            # 清理规则日志
            deleted_rule_logs = session.query(RuleLog).filter(RuleLog.created_at < cutoff_date).delete()
            
            # 清理完成的任务
            deleted_tasks = session.query(TaskQueue).filter(
                TaskQueue.status == 'completed',
                TaskQueue.completed_at < cutoff_date
            ).delete()
            
            session.commit()
            logger.info(f"清理完成: 错误日志 {deleted_errors} 条, 规则日志 {deleted_rule_logs} 条, 任务 {deleted_tasks} 个")
            return deleted_errors + deleted_rule_logs + deleted_tasks
    except Exception as e:
        logger.error(f"清理日志失败: {str(e)}")
        return 0


async def async_cleanup_old_logs(days=30):
    """异步清理旧日志"""
    try:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with AsyncSessionManager() as session:
            # 清理错误日志
            deleted_errors = await session.execute(
                delete(ErrorLog).where(ErrorLog.created_at < cutoff_date)
            )
            deleted_errors = deleted_errors.rowcount
            
            # 清理规则日志
            deleted_rule_logs = await session.execute(
                delete(RuleLog).where(RuleLog.created_at < cutoff_date)
            )
            deleted_rule_logs = deleted_rule_logs.rowcount
            
            # 清理完成的任务
            deleted_tasks = await session.execute(
                delete(TaskQueue).where(
                    TaskQueue.status == 'completed',
                    TaskQueue.completed_at < cutoff_date
                )
            )
            deleted_tasks = deleted_tasks.rowcount
            
            await session.commit()
            logger.info(f"异步清理完成: 错误日志 {deleted_errors} 条, 规则日志 {deleted_rule_logs} 条, 任务 {deleted_tasks} 个")
            return deleted_errors + deleted_rule_logs + deleted_tasks
    except Exception as e:
        logger.error(f"异步清理日志失败: {str(e)}")
        return 0

def init_db():
    """初始化数据库"""
    # 防止 Web 子进程重复执行迁移（假设子进程不应该负责 DDL）
    if os.environ.get('IS_WEB_PROCESS') == 'true':
        return get_engine()

    engine = get_engine()

    # 首先创建所有表
    Base.metadata.create_all(engine)

    # 然后进行必要的迁移
    migrate_db(engine)

    try:
        dedup_engine = get_dedup_engine()
        MediaSignature.__table__.create(dedup_engine, checkfirst=True)
        with dedup_engine.connect() as conn:
            for sql in [
                'CREATE INDEX IF NOT EXISTS idx_media_signatures_chat_signature ON media_signatures(chat_id, signature)',
                'CREATE INDEX IF NOT EXISTS idx_media_signatures_chat_count ON media_signatures(chat_id, count)',
                'CREATE INDEX IF NOT EXISTS idx_media_signatures_type_size ON media_signatures(media_type, file_size)',
                'CREATE INDEX IF NOT EXISTS idx_media_signatures_last_seen ON media_signatures(last_seen)'
            ]:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
        try:
            _auto_migrate_media_signatures(engine, dedup_engine)
        except Exception as e:
            logger.warning(f"自动迁移主库签名到分库失败: {e}")
    except Exception as e:
        logger.warning(f"初始化去重分库结构失败: {e}")

    return engine

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    engine = init_db()
    session = get_session()
    logger.info("数据库初始化和迁移完成。")

def _auto_migrate_media_signatures(main_engine, dedup_engine, batch_size: int = 50000):
    """在初始化时自动将主库的 media_signatures 迁移到分库（仅在分库为空时执行）。"""
    try:
        main_url = str(main_engine.url)
        dedup_url = str(dedup_engine.url)
        if main_url == dedup_url:
            return
        with main_engine.connect() as mconn, dedup_engine.connect() as dconn:
            # 检查迁移标记
            migrated = False
            try:
                res = mconn.execute(text("SELECT value FROM system_configurations WHERE key='dedup_migrated'"))
                row = res.fetchone()
                migrated = bool(row and str(row[0]) in ('1','true','yes'))
            except Exception:
                migrated = False
            if migrated:
                return
            # 统计两侧数量
            try:
                mcount = mconn.execute(text("SELECT COUNT(*) FROM media_signatures")).fetchone()[0]
            except Exception:
                mcount = 0
            try:
                dcount = dconn.execute(text("SELECT COUNT(*) FROM media_signatures")).fetchone()[0]
            except Exception:
                dcount = 0
            if mcount <= 0 or dcount > 0:
                return
            last_id = 0
            total = 0
            cols = ['chat_id','signature','file_id','content_hash','message_id','created_at','updated_at','count','media_type','file_size','file_name','mime_type','duration','width','height','last_seen']
            while True:
                rows = mconn.execute(text(
                    "SELECT id, chat_id, signature, file_id, content_hash, message_id, created_at, updated_at, count, media_type, file_size, file_name, mime_type, duration, width, height, last_seen "
                    "FROM media_signatures WHERE id > :last_id ORDER BY id LIMIT :limit"
                ), {"last_id": last_id, "limit": batch_size}).fetchall()
                if not rows:
                    break
                payload = []
                for r in rows:
                    last_id = r[0]
                    payload.append({
                        'chat_id': r[1], 'signature': r[2], 'file_id': r[3], 'content_hash': r[4],
                        'message_id': r[5], 'created_at': r[6], 'updated_at': r[7], 'count': r[8],
                        'media_type': r[9], 'file_size': r[10], 'file_name': r[11], 'mime_type': r[12],
                        'duration': r[13], 'width': r[14], 'height': r[15], 'last_seen': r[16]
                    })
                placeholders = ', '.join([f":{c}" for c in cols])
                columns_str = ', '.join(cols)
                dconn.execute(text(f"INSERT INTO media_signatures ({columns_str}) VALUES ({placeholders})"), payload)
                total += len(payload)
            # 写入迁移标记
            try:
                mconn.execute(text(
                    "INSERT OR REPLACE INTO system_configurations(key, value, data_type, description) "
                    "VALUES('dedup_migrated', '1', 'boolean', '自动迁移主库签名到分库完成')"
                ))
            except Exception:
                pass
            # 迁移完成后，清理持久化去重缓存，避免旧会话命中导致规则行为误判为“被转移”
            try:
                from utils.db.persistent_cache import get_persistent_cache
                pc = get_persistent_cache()
                cleared = 0
                for prefix in ["dedup:sig:", "dedup:hash:", "video:hash:"]:
                    try:
                        cleared += int(pc.delete_prefix(prefix))
                    except Exception:
                        pass
                logger.info(f"自动迁移 media_signatures 完成，共迁移 {total} 条；已清理持久化去重缓存键 {cleared} 条")
            except Exception:
                logger.info(f"自动迁移 media_signatures 完成，共迁移 {total} 条；持久化缓存清理步骤跳过")
    except Exception as e:
        logger.warning(f"自动迁移过程失败: {e}")
