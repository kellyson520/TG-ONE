import logging
from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry
from handlers.button.callback.search_callback import get_search_callback_handler

logger = logging.getLogger(__name__)

@MenuHandlerRegistry.register
class SearchMenuStrategy(BaseMenuHandler):
    """
    Handles Search-related actions, delegating to SearchCallbackHandler.
    """
    ACTIONS = {
        "search_page", "search_filter", "search_sort",
        "search_set_type", "search_set_sort", "search_toggle_chat_type",
        "search_apply", "search_back", "search_refresh",
        "search_new", "search_bind", "search_detail"
    }

    async def match(self, action: str, **kwargs) -> bool:
        return action in self.ACTIONS

    async def handle(self, event, action: str, **kwargs):
        handler = get_search_callback_handler()
        extra_data = kwargs.get("extra_data", [])
        
        # Parse arguments consistent with SearchCallbackHandler logic
        # operation is usually extra_data[0]
        # query/rest is usually extra_data[1] (or combined rest if originally split with maxsplit)
        
        # Since extra_data is fully split, we might need to rejoin for 'query' if it contained colons?
        # SearchCallbackHandler used split(":", 2), so the 3rd part was the rest.
        # Here extra_data is split by all colons.
        # So operation = extra_data[0]
        # rest = ":".join(extra_data[1:])
        
        operation = extra_data[0] if len(extra_data) > 0 else ""
        rest = ":".join(extra_data[1:]) if len(extra_data) > 1 else ""

        try:
            if action == "search_page":
                await handler._handle_page_change(event, operation, rest)
            elif action == "search_filter":
                await handler._handle_filter_menu(event, operation) # operation is query here?
                # Check search_callback.py: 
                # elif action == "search_filter": await self._handle_filter_menu(event, operation)
                # Yes, acts as query.
            elif action == "search_sort":
                await handler._handle_sort_menu(event, operation)
            elif action == "search_set_type":
                await handler._handle_set_search_type(event, operation, rest)
            elif action == "search_set_sort":
                await handler._handle_set_sort(event, operation, rest)
            elif action == "search_toggle_chat_type":
                await handler._handle_toggle_chat_type(event, operation, rest)
            elif action == "search_apply":
                await handler._handle_apply_filters(event, operation)
            elif action == "search_back":
                await handler._handle_back_to_search(event, operation)
            elif action == "search_refresh":
                await handler._handle_refresh_search(event, operation)
            elif action == "search_new":
                await handler._handle_new_search(event)
            elif action == "search_bind":
                await handler._handle_bind_chat(event, operation)
            elif action == "search_detail":
                await handler._handle_show_detail(event, operation)
        except Exception as e:
            logger.error(f"SearchStrategy Error: {e}", exc_info=True)
            await event.answer("搜索操作失败")
