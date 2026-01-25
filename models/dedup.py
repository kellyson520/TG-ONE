from sqlalchemy import Column, Integer, String, UniqueConstraint
from models.base import Base

class MediaSignature(Base):
    __tablename__ = 'media_signatures'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, nullable=False, index=True)
    signature = Column(String, nullable=False, index=True) # Hash of media
    file_type = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    last_seen = Column(String, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'signature', name='unique_chat_signature'),
    )
