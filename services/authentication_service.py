from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
import jwt
from sqlalchemy.orm import selectinload
from core.config import settings
from models.models import User, ActiveSession
from werkzeug.security import check_password_hash
from sqlalchemy import select, delete, desc
import logging
import hashlib
import uuid
import pyotp
import qrcode
import io
import base64
import secrets
import json

logger = logging.getLogger(__name__)

from schemas.user import UserAuthDTO, UserDTO

class AuthenticationService:
    async def authenticate_user(self, username: str, password: str) -> Optional[UserAuthDTO]:
        """Validate credentials and return user model."""
        logger.info(f"🔐 [Auth] 用户认证请求: 用户名={username}")
        
        from core.container import container
        user = await container.user_repo.get_user_for_auth(username)
        
        if not user:
            logger.warning(f"⚠️ [Auth] 用户认证失败: 用户名不存在，用户名={username}")
            return None
        if not user.password:
            logger.warning(f"⚠️ [Auth] 用户认证失败: 密码为空，用户名={username}")
            return None
        if not check_password_hash(user.password, password):
            logger.warning(f"⚠️ [Auth] 用户认证失败: 密码错误，用户名={username}")
            return None
        if not getattr(user, 'is_active', True): # Default true if missing
            logger.warning(f"⚠️ [Auth] 用户认证失败: 用户已禁用，用户名={username}")
            return None
        
        logger.info(f"✅ [Auth] 用户认证成功: 用户名={username}, 用户ID={user.id}")
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create short-lived access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({
            "exp": expire, 
            "type": "access",
            "jti": secrets.token_hex(8) # Add nonce for uniqueness
        })
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create long-lived refresh token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({
            "exp": expire, 
            "type": "refresh",
            "jti": secrets.token_hex(16) # Add stronger nonce for refresh tokens
        })
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def create_pre_auth_token(self, user_id: int) -> str:
        """Create short-lived pre-auth token for 2FA verification."""
        expire = datetime.utcnow() + timedelta(minutes=5)
        to_encode = {"sub": str(user_id), "type": "pre_auth", "exp": expire}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


    async def create_session(self, user_id: int, ip_address: str, user_agent: str) -> Tuple[str, str]:
        """Create DB session and return (access_token, refresh_token)."""
        logger.info(f"🆕 [Auth] 创建会话: 用户ID={user_id}, IP={ip_address}")
        
        # Tokens store user_id in 'sub'
        access_token = self.create_access_token({"sub": str(user_id)})
        refresh_token = self.create_refresh_token({"sub": str(user_id)})
        
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        from core.container import container
        async with container.db.session() as session:
            try:
                # Store SHA256 hash of refresh token
                token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
                new_session = ActiveSession(
                    session_id=str(uuid.uuid4()),
                    user_id=user_id,
                    refresh_token_hash=token_hash,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    expires_at=expires_at,
                    created_at=datetime.utcnow()
                )
                session.add(new_session)
                await session.commit()
                
                logger.info(f"✅ [Auth] 会话创建成功: 用户ID={user_id}, IP={ip_address}, 会话ID={new_session.session_id}")
            except Exception as e:
                logger.error(f"❌ [Auth] 会话创建失败: 用户ID={user_id}, IP={ip_address}, 错误={e}")
                raise e
            
        return access_token, refresh_token

    async def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        Use refresh token to get a new access token.
        Implements Rotation: Generates a new refresh token and replaces the old one.
        """
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                return None
            user_id_str = payload.get("sub")
            if not user_id_str:
                return None
            user_id = int(user_id_str)
        except (jwt.InvalidTokenError, ValueError):
            return None

        from core.container import container
        async with container.db.session() as session:
            # Check if session exists in DB (by hash)
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            stmt = select(ActiveSession).where(ActiveSession.refresh_token_hash == token_hash)
            result = await session.execute(stmt)
            active_session = result.scalar_one_or_none()
            
            if not active_session:
                # Token valid signature but not in DB -> Potential Token Reuse or Revoked
                logger.warning(f"Refresh token reuse detected or revoked token used: {user_id}")
                return None
            
            # Check expiration
            if active_session.expires_at < datetime.utcnow():
                await session.delete(active_session)
                await session.commit()
                return None

            # Rotation: Generate new tokens
            new_access_token = self.create_access_token({"sub": str(user_id)})
            new_refresh_token = self.create_refresh_token({"sub": str(user_id)})
            new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
            
            # Update session in DB
            active_session.refresh_token_hash = new_token_hash
            active_session.last_active_at = datetime.utcnow()
            # Update expires_at to extend session? Usually refresh tokens have their own TTL.
            # For now, keep original expiration or extend slightly.
            active_session.expires_at = datetime.utcnow() + timedelta(days=7)
            
            await session.commit()
            
            return new_access_token, new_refresh_token

    async def revoke_session(self, refresh_token: str):
        """Revoke a single session by refresh token."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        from core.container import container
        async with container.db.session() as session:
            stmt = delete(ActiveSession).where(ActiveSession.refresh_token_hash == token_hash)
            await session.execute(stmt)
            await session.commit()

    async def revoke_session_by_id(self, session_id: int):
        """Revoke a single session by ID (Admin)."""
        from core.container import container
        async with container.db.session() as session:
            stmt = delete(ActiveSession).where(ActiveSession.id == session_id)
            await session.execute(stmt)
            await session.commit()

    async def revoke_user_sessions(self, user_id: int):
        """Revoke all sessions for a user."""
        from core.container import container
        async with container.db.session() as session:
            stmt = delete(ActiveSession).where(ActiveSession.user_id == user_id)
            await session.execute(stmt)
            await session.commit()

    async def get_user_from_token(self, token: str) -> Optional[UserDTO]:
        """Decode access token and return User object."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") != "access": # Enforce type check
                return None
            user_id = payload.get("sub")
            if not user_id:
                return None
                
            # Use repository to fetch user
            from core.container import container
            return await container.user_repo.get_user_by_id(int(user_id))
        except Exception as e:
            # logger.debug(f"Token validation failed: {e}")
            return None

    async def get_active_sessions(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get list of active sessions."""
        from core.container import container
        async with container.db.session() as session:
            stmt = select(ActiveSession).options(selectinload("user"))
            
            # Join user to get username if needed, but ActiveSession has user_id
            # For admin view, we might want user details.
            
            if user_id:
                stmt = stmt.where(ActiveSession.user_id == user_id)
            
            stmt = stmt.order_by(desc(ActiveSession.created_at))
            result = await session.execute(stmt)
            sessions = result.scalars().all()
            
            # Format output
            return [{
                "id": s.id,
                "user_id": s.user_id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "is_active": s.expires_at > datetime.utcnow()
            } for s in sessions]

    async def generate_2fa_secret(self, user_id: int) -> Tuple[str, str, str]:
        """
        Generate a new TOTP secret for the user.
        Returns (secret, otpauth_url, qr_code_base64)
        """
        secret = pyotp.random_base32()
        
        from core.container import container
        async with container.db.session() as session:
             stmt = select(User).where(User.id == user_id)
             result = await session.execute(stmt)
             user = result.scalar_one_or_none()
             if not user:
                 raise ValueError("User not found")
             
             # Save secret to DB (but don't enable yet)
             user.totp_secret = secret
             user.is_2fa_enabled = False # Ensure false until verified
             await session.commit()
             
             # Generate Provisioning URI
             issuer_name = "TG Forwarder"
             provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=issuer_name)
             
             # Generate QR Code image
             qr = qrcode.QRCode(version=1, box_size=10, border=5)
             qr.add_data(provisioning_uri)
             qr.make(fit=True)
             img = qr.make_image(fill_color="black", back_color="white")
             
             buffered = io.BytesIO()
             img.save(buffered, format="PNG")
             qr_b64 = base64.b64encode(buffered.getvalue()).decode()
             
             return secret, provisioning_uri, qr_b64

    async def verify_and_enable_2fa(self, user_id: int, token: str) -> bool:
        """Verify the token and enable 2FA if correct."""
        from core.container import container
        async with container.db.session() as session:
             stmt = select(User).where(User.id == user_id)
             result = await session.execute(stmt)
             user = result.scalar_one_or_none()
             
             if not user or not user.totp_secret:
                 return False
                 
             totp = pyotp.TOTP(user.totp_secret)
             if totp.verify(token):
                 # Anti-replay check
                 if user.last_otp_token == token:
                     logger.warning(f"TOTP replay detected for user {user_id}")
                     return False
                 
                 user.last_otp_token = token
                 user.last_otp_at = datetime.utcnow().isoformat()
                 user.is_2fa_enabled = True
                 await session.commit()
                 return True
             return False

    async def verify_2fa_login(self, user_id: int, token: str) -> bool:
        """Verify TOTP token for login."""
        from core.container import container
        user = await container.user_repo.get_user_auth_by_id(user_id)
        
        if not user or not user.is_2fa_enabled or not user.totp_secret:
            return False
            
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(token):
            # Update user in DB
            async with container.db.session() as session:
                db_user = await session.get(User, user.id)
                if not db_user:
                    return False
                    
                # Anti-replay check (Must use db_user here!)
                if db_user.last_otp_token == token:
                    logger.warning(f"TOTP replay detected for user {user.id}")
                    return False
                
                db_user.last_otp_token = token
                db_user.last_otp_at = datetime.utcnow().isoformat()
                await session.commit()
            return True
        return False

    async def disable_2fa(self, user_id: int) -> bool:
        """Disable 2FA for a user."""
        from core.container import container
        async with container.db.session() as session:
             stmt = select(User).where(User.id == user_id)
             result = await session.execute(stmt)
             user = result.scalar_one_or_none()
             if user:
                 user.is_2fa_enabled = False
                 user.totp_secret = None
                 user.backup_codes = None  # 清理备份码
                 await session.commit()
                 return True
        return False

    # ===== Recovery Codes (备份码) =====
    
    def _generate_recovery_codes(self, count: int = 10) -> List[str]:
        """
        生成一组备份码
        
        格式: XXXX-XXXX (8位字母数字，中间横杠分隔)
        每个备份码只能使用一次
        
        Args:
            count: 生成备份码数量 (默认 10 个)
            
        Returns:
            明文备份码列表 (需要展示给用户，后续只存储哈希)
        """
        codes = []
        for _ in range(count):
            # 生成 8 个字符的随机码
            code = secrets.token_hex(4).upper()  # 8 hex chars
            # 格式化为 XXXX-XXXX
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes
    
    def _hash_recovery_codes(self, codes: List[str]) -> List[Dict]:
        """
        对备份码进行哈希处理
        
        Returns:
            [{"hash": "...", "used": False}, ...]
        """
        hashed = []
        for code in codes:
            # 使用 SHA256 哈希
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            hashed.append({"hash": code_hash, "used": False})
        return hashed
    
    async def generate_recovery_codes(self, user_id: int) -> List[str]:
        """
        为用户生成新的备份码并保存到数据库
        
        注意: 此方法会覆盖之前的备份码！
        
        Args:
            user_id: 用户 ID
            
        Returns:
            明文备份码列表 (仅此一次展示机会)
        """
        from core.container import container
        async with container.db.session() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # 生成新备份码
            plain_codes = self._generate_recovery_codes(10)
            hashed_codes = self._hash_recovery_codes(plain_codes)
            
            # 保存哈希后的备份码到数据库
            user.backup_codes = json.dumps(hashed_codes)
            await session.commit()
            
            logger.info(f"Generated 10 recovery codes for user {user_id}")
            return plain_codes
    
    async def verify_recovery_code(self, user_id: int, code: str) -> bool:
        """
        验证并消费一个备份码
        
        如果验证成功，该备份码会被标记为已使用
        
        Args:
            user_id: 用户 ID
            code: 用户输入的备份码 (格式: XXXX-XXXX)
            
        Returns:
            True 如果验证成功
        """
        from core.container import container
        
        # 标准化输入 (去除空格，转大写)
        code = code.strip().upper().replace(" ", "")
        
        async with container.db.session() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user or not user.backup_codes:
                return False
            
            try:
                codes = json.loads(user.backup_codes)
            except json.JSONDecodeError:
                logger.error(f"Invalid backup_codes JSON for user {user_id}")
                return False
            
            # 计算输入码的哈希
            input_hash = hashlib.sha256(code.encode()).hexdigest()
            
            # 查找匹配的未使用备份码
            for i, entry in enumerate(codes):
                if entry["hash"] == input_hash and not entry["used"]:
                    # 标记为已使用
                    codes[i]["used"] = True
                    user.backup_codes = json.dumps(codes)
                    await session.commit()
                    
                    logger.info(f"Recovery code verified and consumed for user {user_id}")
                    return True
            
            logger.warning(f"Invalid or already used recovery code for user {user_id}")
            return False
    
    async def get_recovery_codes_status(self, user_id: int) -> Dict:
        """
        获取用户备份码状态
        
        Returns:
            {
                "total": 10,
                "used": 2,
                "remaining": 8,
                "has_codes": True
            }
        """
        from core.container import container
        async with container.db.session() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user or not user.backup_codes:
                return {
                    "total": 0,
                    "used": 0,
                    "remaining": 0,
                    "has_codes": False
                }
            
            try:
                codes = json.loads(user.backup_codes)
                total = len(codes)
                used = sum(1 for c in codes if c.get("used", False))
                return {
                    "total": total,
                    "used": used,
                    "remaining": total - used,
                    "has_codes": True
                }
            except json.JSONDecodeError:
                return {
                    "total": 0,
                    "used": 0,
                    "remaining": 0,
                    "has_codes": False
                }


authentication_service = AuthenticationService()

