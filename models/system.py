from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from models.base import Base

class SystemConfiguration(Base):
    """系统配置表"""
    __tablename__ = 'system_configurations'
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(String, nullable=True)
    data_type = Column(String, default='string')
    description = Column(String, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())

class ErrorLog(Base):
    """错误日志表"""
    __tablename__ = 'error_logs'
    id = Column(Integer, primary_key=True)
    level = Column(String, nullable=False, index=True) # ERROR, WARNING, etc.
    module = Column(String, nullable=True, index=True)
    message = Column(String, nullable=False)
    traceback = Column(String, nullable=True)
    is_traceback_compressed = Column(Boolean, default=False)
    rule_id = Column(Integer, nullable=True)
    chat_id = Column(String, nullable=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat(), index=True)

class TaskQueue(Base):
    """任务队列表"""
    __tablename__ = 'task_queue'
    id = Column(Integer, primary_key=True)
    task_type = Column(String, nullable=False, index=True)
    task_data = Column(String, nullable=True)
    status = Column(String, default='pending', index=True) # pending, processing, completed, failed
    priority = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    locked_until = Column(DateTime, nullable=True, index=True) # 用于"可见性超时"模式
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Context
    source_chat_id = Column(String, nullable=True)
    target_chat_id = Column(String, nullable=True)
    unique_key = Column(String, unique=True, index=True, nullable=True)
    grouped_id = Column(String, index=True, nullable=True)

class RSSSubscription(Base):
    """外部 RSS 订阅表"""
    __tablename__ = 'rss_subscriptions'
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    target_chat_id = Column(String, nullable=False)
    last_guid = Column(String, nullable=True)
    last_published = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    min_interval = Column(Integer, default=300)
    max_interval = Column(Integer, default=3600)
    current_interval = Column(Integer, default=600)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
