from pydantic import BaseModel
from typing import Optional, List

# Basic Keywords, Replacements
class KeywordDTO(BaseModel):
    id: int
    keyword: str
    is_regex: bool = False
    is_blacklist: bool = True
    
    class Config:
        from_attributes = True

class ReplaceRuleDTO(BaseModel):
    id: int
    pattern: str
    content: Optional[str] = None
    is_regex: bool = False
    
    class Config:
        from_attributes = True
