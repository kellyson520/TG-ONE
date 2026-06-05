import asyncio
import logging
import sys
import os

# 将项目根目录加入 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db_init import init_hotword_db

async def test_init():
    logging.basicConfig(level=logging.INFO)
    try:
        await init_hotword_db()
        print("Successfully initialized/verified hotword database.")
    except Exception as e:
        print(f"Failed to initialize hotword database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_init())
