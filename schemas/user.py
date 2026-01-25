from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List
from .common import TimestampMixin

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    telegram_id: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    
class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    telegram_id: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    password: Optional[str] = None

class UserDTO(UserBase, TimestampMixin):
    id: int
    last_login: Optional[str] = None
    login_count: int = 0
    is_2fa_enabled: bool = False
    
    # 2FA fields we might want to expose internaly?
    # but strictly speaking DTO should be safe.
    # We add totp_secret if really needed but better keep it separate.

    model_config = ConfigDict(from_attributes=True)

class UserAuthDTO(UserDTO):
    """
    DTO for internal authentication use, including password hash and 2FA secrets.
    NEVER return this to API clients.
    """
    password: str
    totp_secret: Optional[str] = None
    backup_codes: Optional[str] = None
    last_otp_token: Optional[str] = None
    last_otp_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
