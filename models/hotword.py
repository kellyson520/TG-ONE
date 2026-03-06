from sqlalchemy import Column, String, Float, Integer, JSON, TIMESTAMP, Index, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class HotRawStats(Base):
    """存储频道内的实时增量 (对应原 _temp.json)"""
    __tablename__ = 'hot_raw_stats'
    
    channel = Column(String(100), primary_key=True)
    word = Column(String(100), primary_key=True)
    score = Column(Float, default=0.0)
    unique_users = Column(Integer, default=0)
    last_update = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class HotPeriodStats(Base):
    """存储归类后的历史榜单 (day, month, year)"""
    __tablename__ = 'hot_period_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(100), nullable=False)
    word = Column(String(100), nullable=False)
    period = Column(String(20), nullable=False) # 'day', 'month', 'year'
    date_key = Column(String(20), nullable=False) # e.g., '20260306'
    score = Column(Float, default=0.0)
    user_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_hot_period_lookup', 'channel', 'period', 'date_key'),
        Index('idx_hot_period_date', 'period', 'date_key'),
    )

class HotConfig(Base):
    """存储热词配置 (黑名单、白名单、噪声词)"""
    __tablename__ = 'hot_config'
    
    name = Column(String(50), primary_key=True) # 'white', 'black', 'noise'
    data = Column(JSON, nullable=False) # 存储具体词汇列表或权重字典
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
