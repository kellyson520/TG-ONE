from pydantic import BaseModel, Field
from typing import Optional

class BaseTaskPayload(BaseModel):
    v: int = Field(default=1, alias="_v") # 版本控制
    chat_id: int
    message_id: int
    source: str = "telegram"

class ProcessMessagePayload(BaseTaskPayload):
    has_media: bool = False
    manual_trigger: bool = False

class DownloadFilePayload(BaseTaskPayload):
    file_id: Optional[str] = None
    sub_folder: Optional[str] = None

# 使用示例 (在 Listener 中):
# payload = ProcessMessagePayload(chat_id=event.chat_id, message_id=event.id, has_media=True)
# await task_repo.push("process_message", payload.model_dump())