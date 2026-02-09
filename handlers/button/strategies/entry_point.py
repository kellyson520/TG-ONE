from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry

@MenuHandlerRegistry.register
class EchoMenuHandler(BaseMenuHandler):
    """
    A simple Echo Handler to verify the registry and routing logic works.
    Matches actions starting with 'echo'.
    """

    async def match(self, action: str, **kwargs) -> bool:
        return action.startswith("echo")

    async def handle(self, event, action: str, **kwargs):
        content = action.split(":", 1)[1] if ":" in action else "No content"
        await event.answer(f"Echo: {content}", alert=True)
