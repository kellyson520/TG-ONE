from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class ChatStatistics(Base):
    """聊天统计表"""
    __tablename__ = 'chat_statistics'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False, index=True)
    date = Column(String, nullable=False, index=True) # YYYY-MM-DD
    message_count = Column(Integer, default=0)
    forward_count = Column(Integer, default=0)
    saved_traffic_bytes = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chat = relationship('Chat', back_populates='chat_stats')
    __table_args__ = (
        UniqueConstraint('chat_id', 'date', name='unique_chat_date_stats'),
    )

class RuleStatistics(Base):
    """规则统计表"""
    __tablename__ = 'rule_statistics'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, index=True)
    date = Column(String, nullable=False, index=True) # YYYY-MM-DD
    total_triggered = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    filtered_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    rule = relationship('ForwardRule', back_populates='rule_statistics')
    __table_args__ = (
        UniqueConstraint('rule_id', 'date', name='unique_rule_date_stats'),
    )

class RuleLog(Base):
    """规则操作日志表"""
    __tablename__ = 'rule_logs'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('forward_rules.id'), nullable=False, index=True)
    action = Column(String, nullable=False) # forwarded, filtered, error
    message_id = Column(Integer, nullable=True)
    message_text = Column(String, nullable=True) # 用于详情展示与搜索
    message_type = Column(String, nullable=True) # text, photo, video, etc.
    processing_time = Column(Integer, nullable=True) # 处理耗时 (ms)
    details = Column(String, nullable=True)
    is_result_compressed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    rule = relationship('ForwardRule', back_populates='rule_logs')
