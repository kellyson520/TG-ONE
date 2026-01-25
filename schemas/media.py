from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class MediaSignatureDTO(BaseModel):
    id: Optional[int] = None
    chat_id: str
    signature: str
    file_id: Optional[str] = None
    content_hash: Optional[str] = None
    count: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_seen: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
