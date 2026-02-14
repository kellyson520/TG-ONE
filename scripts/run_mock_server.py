
import sys
import os
import asyncio
import platform
import logging
import signal

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.logging import setup_logging
# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Set event loop policy for Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.config import settings
from core.container import container
from scripts.mock_telegram_client import MockTelegramClient
from web_admin.fastapi_app import start_web_server

async def main():
    print("🚀 Starting Mock API Server...")

    # 1. Initialize Mock Clients
    user_client = MockTelegramClient("session_user", 12345, "mock_hash")
    bot_client = MockTelegramClient("session_bot", 12345, "mock_hash")

    # Start mocks
    await user_client.start()
    await bot_client.start()

    # 2. Initialize Container with Mocks
    # This dependency injection fools the rest of the application
    container.init_with_client(user_client, bot_client)
    
    # 3. Initialize DB (Required for some API endpoints)
    # We use the real DB connection, but you could mock this too if needed.
    # The container automatically connects to the real DB on init.
    
    pass # DB is already init in container.__init__

    # 4. Start Web Server
    host = settings.WEB_HOST
    port = settings.WEB_PORT
    
    print(f"🌍 Web Server listening at http://{host}:{port}")
    print("✅ Mock Telegram Clients Active")
    print("❌ Real Telegram Connection Disabled")
    
    try:
        await start_web_server(host, port)
    except asyncio.CancelledError:
        print("Server stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
