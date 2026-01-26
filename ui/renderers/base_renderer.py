from typing import Dict, Any, List
from telethon.tl.custom import Button
import logging

logger = logging.getLogger(__name__)

class BaseRenderer:
    """基础渲染器类"""
    def create_back_button(self, callback_data: str, label: str = "👈 返回") -> List[Button]:
        return [Button.inline(label, callback_data)]
        
    def create_error_view(self, title: str, message: str, back_callback: str) -> Dict[str, Any]:
        return {
            'text': f"❌ **{title}**\n\n{message}",
            'buttons': [self.create_back_button(back_callback)]
        }
