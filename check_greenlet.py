import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import greenlet

async def main():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print(f"Current greenlet: {greenlet.getcurrent()}")
        await session.execute(text("SELECT 1"))
        print("Executed SELECT 1")
        try:
            await session.rollback()
            print("Rollback successful")
        except Exception as e:
            print(f"Rollback failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
