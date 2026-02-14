import asyncio
from typing import Optional, List, Union, AsyncGenerator
from unittest.mock import MagicMock
from datetime import datetime

class MockUser:
    def __init__(self, id: int, username: str, first_name: str, bot: bool = False):
        self.id = id
        self.username = username
        self.first_name = first_name
        self.bot = bot
        self.phone = "+1234567890"

class MockMessage:
    def __init__(self, id: int, text: str, date: datetime):
        self.id = id
        self.text = text
        self.date = date
        self.raw_text = text
        self.message = text
        self.sender_id = 123456789
        self.chat_id = 987654321
        self.media = None

class MockTelegramClient:
    """
    A minimal mock of Telethon's TelegramClient for running the API server without connecting to Telegram.
    """
    def __init__(self, session: str, api_id: int, api_hash: str):
        self.session_name = session
        self.api_id = api_id
        self.api_hash = api_hash
        self._connected = False
        self.loop = asyncio.get_event_loop()

    async def start(self, bot_token: Optional[str] = None, phone: Optional[str] = None):
        print(f"[MockClient] Starting client (Session: {self.session_name})...")
        self._connected = True
        return self

    async def connect(self):
        print(f"[MockClient] Connecting...")
        self._connected = True

    async def disconnect(self):
        print(f"[MockClient] Disconnecting...")
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def get_me(self) -> MockUser:
        if "bot" in self.session_name:
            return MockUser(12345, "mock_bot", "Mock Bot", bot=True)
        return MockUser(67890, "mock_user", "Mock User", bot=False)

    async def get_messages(self, entity, limit: int = 10, **kwargs) -> List[MockMessage]:
        print(f"[MockClient] get_messages(entity={entity}, limit={limit})")
        return []

    async def iter_messages(self, entity, limit: int = 10, **kwargs) -> AsyncGenerator[MockMessage, None]:
        print(f"[MockClient] iter_messages(entity={entity}, limit={limit})")
        for i in range(limit or 0):
            yield MockMessage(i, f"Mock Message {i}", datetime.now())

    async def send_message(self, entity, message: str, **kwargs):
        print(f"[MockClient] send_message(entity={entity}, message='{message}')")
        return MockMessage(999, message, datetime.now())

    async def get_input_entity(self, peer):
        return MagicMock()

    async def get_entity(self, peer):
        return MagicMock()
        
    def __call__(self, request):
        """Mock handling of raw requests"""
        print(f"[MockClient] Received request: {type(request)}")
        return MagicMock() 

