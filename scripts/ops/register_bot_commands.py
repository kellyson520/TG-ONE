import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from telethon import TelegramClient
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommandScopeDefault
from core.config import settings
from handlers.bot_commands_list import BOT_COMMANDS

async def main():
    print("🚀 Starting manual command registration...")
    
    # Use a temporary session to avoid database locks with the running bot
    session_path = os.path.join(settings.DATA_DIR, "temp_registry_session")
    
    try:
        client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)
        await client.start(bot_token=settings.BOT_TOKEN)
        
        print(f"📦 Loaded {len(BOT_COMMANDS)} commands from handlers.bot_commands_list")
        
        print("📡 Sending SetBotCommandsRequest to Telegram...")
        await client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=BOT_COMMANDS
        ))
        
        print("✅ Commands successfully registered!")
        
        me = await client.get_me()
        print(f"🤖 Bot: @{me.username}")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Cleanup temp session
        if os.path.exists(session_path + ".session"):
            try:
                os.remove(session_path + ".session")
                print("🧹 Cleaned up temp session.")
            except:
                pass

if __name__ == '__main__':
    asyncio.run(main())
