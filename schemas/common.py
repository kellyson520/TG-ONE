from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Any

class TimestampMixin(BaseModel):
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class PaginationQuery(BaseModel):
    page: int = 1
    page_size: int = 20
    
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
