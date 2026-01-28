from pydantic import BaseModel, ConfigDict
from typing import Optional
from .common import TimestampMixin

class ChatBase(BaseModel):
    telegram_chat_id: str
    name: Optional[str] = None
    username: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    member_count: Optional[int] = None

class ChatCreate(ChatBase):
    pass

class ChatUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    member_count: Optional[int] = None

class ChatDTO(ChatBase, TimestampMixin):
    id: int
    current_add_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
