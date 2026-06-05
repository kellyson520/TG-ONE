
import asyncio
import os
import sys
import logging

# Ensure project root is in path
sys.path.append(os.getcwd())

from telethon import TelegramClient
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommandScopeDefault

from core.config import settings
from handlers.bot_commands_list import BOT_COMMANDS

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 开始强制注册 Bot 命令...")
    
    # Initialize Bot Client
    bot_client = TelegramClient(
        str(settings.SESSION_DIR / "bot"), 
        settings.API_ID, 
        settings.API_HASH
    )
    
    await bot_client.start(bot_token=settings.BOT_TOKEN)
    me = await bot_client.get_me()
    logger.info(f"✅ Bot 登录成功: {me.first_name} (@{me.username})")

    try:
        logger.info(f"📋 准备注册 {len(BOT_COMMANDS)} 个命令...")
        
        # 1. Register Default (Empty lang_code)
        await bot_client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=BOT_COMMANDS
        ))
        logger.info("✅ 默认语言 (Default) 命令注册成功")

        # 2. Register Chinese (zh) - to ensure visibility for Chinese users
        await bot_client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='zh',
            commands=BOT_COMMANDS
        ))
        logger.info("✅ 中文 (zh) 命令注册成功")
        
        # 3. Register Chinese Simplified (zh-hans)
        await bot_client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='zh-hans',
            commands=BOT_COMMANDS
        ))
        logger.info("✅ 简体中文 (zh-hans) 命令注册成功")

        print("\n" + "="*50)
        print("🎉 命令列表刷新成功！")
        print("💡 提示: 如果 Telegram 界面未立即更新，请尝试：")
        print("   1. 重启 Telegram 客户端")
        print("   2. 在 Bot 对话中手动输入 '/' 强制触发补全")
        print("   3. 等待几分钟 (Telegram 服务器可能有缓存)")
        print("="*50 + "\n")

    except Exception as e:
        logger.error(f"❌ 注册失败: {e}")
    finally:
        await bot_client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
