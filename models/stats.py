from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean
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
    error_count = Column(Integer, default=0)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
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
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    
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
    details = Column(String, nullable=True)
    is_result_compressed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat(), index=True)
    
    rule = relationship('ForwardRule', back_populates='rule_logs')
