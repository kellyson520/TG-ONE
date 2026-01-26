from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True, index=True)
    password = Column(String, nullable=False)
    email = Column(String, nullable=True)
    telegram_id = Column(String, nullable=True, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    last_login_at = Column(String, nullable=True)
    
    # Security Features
    totp_secret = Column(String, nullable=True)
    is_2fa_enabled = Column(Boolean, default=False)
    backup_codes = Column(String, nullable=True)
    last_otp_token = Column(String, nullable=True)
    last_otp_at = Column(String, nullable=True)

class AuditLog(Base):
    """审计日志表"""
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    username = Column(String, nullable=True)  # 可选：记录操作时的用户名
    action = Column(String, nullable=False, index=True) # login, logout, create_rule, etc.
    resource_type = Column(String, nullable=True) # rule, user, setting, etc.
    resource_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    details = Column(String, nullable=True)
    status = Column(String, default='success')
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship('User', backref='audit_logs')

class ActiveSession(Base):
    """活跃会话表"""
    __tablename__ = 'active_sessions'
    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, index=True) # 区分不同设备的会话
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    refresh_token_hash = Column(String(128), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship('User', backref='sessions')

class AccessControlList(Base):
    """IP 访问控制列表 (ACL)"""
    __tablename__ = 'access_control_list'
    id = Column(Integer, primary_key=True)
    ip_address = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, default='whitelist') # whitelist, blacklist
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint('ip_address', 'type', name='unique_ip_type'),
    )
