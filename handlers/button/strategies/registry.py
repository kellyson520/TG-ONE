import logging
from typing import Dict, Type, Optional, List
from .base import BaseMenuHandler

logger = logging.getLogger(__name__)

class MenuHandlerRegistry:
    """
    Registry for Menu Strategies.
    Implements the Strategy Pattern to dispatch actions to the correct handler.
    """
    _handlers: List[BaseMenuHandler] = []
    _initialized = False

    @classmethod
    def register(cls, handler_cls: Type[BaseMenuHandler]):
        """
        Decorator to register a new handler strategy.
        """
        # We instantiate the handler immediately upon registration
        # In a more complex DI system, we might just store the class
        instance = handler_cls()
        cls._handlers.append(instance)
        logger.info(f"Registered Menu Strategy: {handler_cls.__name__}")
        return handler_cls

    @classmethod
    async def dispatch(cls, event, action: str, **kwargs):
        """
        Iterate through registered handlers and find the one that matches the action.
        Returns:
            bool: True if a handler was found and executed, False otherwise.
        """
        # Sort handlers by priority if needed? For now, first match wins.
        # But we need to ensure specific matches come before wildcard matches if we have them.
        
        for handler in cls._handlers:
            try:
                if await handler.match(action, **kwargs):
                    logger.debug(f"Action '{action}' matched by {handler.__class__.__name__}")
                    await handler.handle(event, action, **kwargs)
                    return True
            except Exception as e:
                logger.error(f"Error in handler match middleware: {e}", exc_info=True)
                continue

        logger.warning(f"No handler found for action: {action}")
        return False

    @classmethod
    def get_registered_handlers(cls):
        return [h.__class__.__name__ for h in cls._handlers]
