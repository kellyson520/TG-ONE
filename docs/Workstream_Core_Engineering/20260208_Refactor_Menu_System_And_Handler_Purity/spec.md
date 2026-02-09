# Refactoring Specification: Menu System Strategy Pattern

## 1. Class Diagram

### Base Handler
```python
class BaseMenuHandler(ABC):
    @abstractmethod
    async def handle(self, event: events.CallbackQuery.Event, action: str, extra_data: list[str]):
        """
        处理菜单回调的核心方法
        :param event: Telethon Event
        :param action: 解析后的动作指令 (e.g., "list_rules")
        :param extra_data: 冒号分隔的额外参数 (e.g., ["123", "enable"])
        """
        pass
```

### Registry
```python
class MenuHandlerRegistry:
    _handlers: Dict[str, BaseMenuHandler] = {}

    @classmethod
    def register(cls, actions: List[str]):
        """装饰器：注册 Handler 处理特定的 actions"""
        def wrapper(handler_cls):
            instance = handler_cls()
            for action in actions:
                cls._handlers[action] = instance
            return handler_cls
        return wrapper

    @classmethod
    async def dispatch(cls, event, action, extra_data):
        handler = cls._handlers.get(action)
        if handler:
            await handler.handle(event, action, extra_data)
        else:
            # Fallback or Log
            logger.warning(f"No handler found for {action}")
```

## 2. Directory Structure Goals

```text
handlers/
  button/
    strategies/
      __init__.py
      registry.py       # The dispatcher
      base.py           # Abstract Base Class
      system.py         # System & Backup handlers
      rules.py          # Rule management
      dedup.py          # Deduplication stuff
      history.py        # History & Time Pickers
      settings.py       # Global settings
```

## 3. Database Access Rules
**Violation:**
```python
# BAD (In Handler)
async with container.db.session() as session:
    user = await session.get(User, event.sender_id)
```

**Correction:**
```python
# GOOD (In Handler)
from services.user_service import user_service
user = await user_service.get_user(event.sender_id)
```
