from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RSSSubscriptionBase(BaseModel):
    url: str = Field(..., description="RSS Feed URL")
    target_chat_id: str = Field(..., description="Target Channel/Group ID")
    rule_id: Optional[int] = Field(None, description="Associated Forward Rule ID")
    is_active: bool = Field(True, description="Is Subscription Active")
    min_interval: int = Field(60, description="Minimum Polling Interval (seconds)")
    max_interval: int = Field(3600, description="Maximum Polling Interval (seconds)")
    current_interval: int = Field(600, description="Current Polling Interval (seconds)")

class RSSSubscriptionCreate(RSSSubscriptionBase):
    pass

class RSSSubscriptionUpdate(BaseModel):
    url: Optional[str] = None
    target_chat_id: Optional[str] = None
    rule_id: Optional[int] = None
    is_active: Optional[bool] = None
    min_interval: Optional[int] = None
    max_interval: Optional[int] = None
    current_interval: Optional[int] = None

class RSSSubscriptionResponse(RSSSubscriptionBase):
    id: int
    last_checked: Optional[datetime] = None
    last_etag: Optional[str] = None
    last_modified: Optional[str] = None
    latest_post_date: Optional[datetime] = None
    fail_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
