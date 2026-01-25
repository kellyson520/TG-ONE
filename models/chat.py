from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from models.base import Base

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True)
    telegram_chat_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    type = Column(String, nullable=True)
    title = Column(String, nullable=True)
    current_add_id = Column(String, nullable=True)
    
    # Relationships
    source_rules = relationship('ForwardRule', foreign_keys='ForwardRule.source_chat_id', back_populates='source_chat')
    target_rules = relationship('ForwardRule', foreign_keys='ForwardRule.target_chat_id', back_populates='target_chat')
    chat_stats = relationship('ChatStatistics', back_populates='chat', cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chat(id={self.id}, tg_id={self.telegram_chat_id}, name='{self.name}')>"
