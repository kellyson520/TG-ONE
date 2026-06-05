from abc import ABC, abstractmethod
from typing import Optional, Any
from telethon.events import CallbackQuery

class BaseMenuHandler(ABC):
    """
    Abstract Base Class for all Menu Strategies.
    enforces a standard interface for handling callbacks.
    """

    @abstractmethod
    async def match(self, action: str, **kwargs) -> bool:
        """
        Determine if this handler should handle the given action.
        This provides flexibility beyond simple string matching (m.g. regex).
        """
        pass

    @abstractmethod
    async def handle(self, event: CallbackQuery, action: str, **kwargs) -> Any:
        """
        Execute the logic for the action.
        
        Args:
            event: The Telethon CallbackQuery event.
            action: The specific action string (e.g., 'main_menu', 'toggle_rule:1').
            **kwargs: Additional context (e.g., rule_id, page).
        
        Returns:
            The result of the operation (usually await event.edit(...) or similar).
        """
        pass
