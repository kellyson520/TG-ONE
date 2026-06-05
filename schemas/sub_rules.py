from pydantic import BaseModel, ConfigDict
from typing import Optional

# Basic Keywords, Replacements
class KeywordDTO(BaseModel):
    id: int
    keyword: str
    is_regex: bool = False
    is_blacklist: bool = True
    
    model_config = ConfigDict(from_attributes=True)

class ReplaceRuleDTO(BaseModel):
    id: int
    pattern: str
    content: Optional[str] = None
    is_regex: bool = False
    
    model_config = ConfigDict(from_attributes=True)
