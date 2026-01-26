from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")

class ResponseSchema(BaseModel, Generic[T]):
    """标准 API 响应结构"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None
    error: Optional[str] = None
    meta: Optional[dict] = None  # 用于分页信息等元数据
