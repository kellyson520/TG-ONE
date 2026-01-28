
import asyncio
import logging
import sys
import os
import json
from datetime import datetime

# Setup paths
sys.path.append(os.getcwd())

# Mocking Telethon classes to avoid full client connection
class MockMessage:
    def __init__(self, id, text="", media=None, grouped_id=None):
        self.id = id
        self.text = text
        self.media = media
        self.grouped_id = grouped_id
        self.date = datetime.utcnow()

class MockClient:
    def __init__(self):
        self.sent_messages = []
        
    def is_connected(self):
        return True
        
    async def connect(self):
        pass
        
    async def get_messages(self, chat_id, ids):
        # Return mock messages
        if isinstance(ids, list):
            return [MockMessage(i, f"Msg {i}", grouped_id="12345" if i in [101, 102, 103] else None) for i in ids]
        return MockMessage(ids, f"Msg {ids}")
        
    async def send_message(self, chat_id, text, file=None):
        print(f"[MockClient] Sending Message to {chat_id}: {text} (File: {file})")
        self.sent_messages.append({"to": chat_id, "text": text, "file": file})
        
    async def send_file(self, chat_id, file, caption=""):
        print(f"[MockClient] Sending File to {chat_id}: {file} (Caption: {caption})")
        self.sent_messages.append({"to": chat_id, "file": file, "caption": caption})

    # Mock forward_messages (Telethon style)
    async def forward_messages(self, entity, messages, from_peer=None):
        print(f"[MockClient] Forwarding messages {messages} to {entity}")
        self.sent_messages.append({"to": entity, "messages": messages, "type": "forward"})

# Setup DB
async def setup_db():
    from core.database import init_db
    await init_db()

async def verify_media_group():
    print("\n=== Verifying Media Group Aggregation ===")
    from core.database import Database
    from repositories.task_repo import TaskRepository
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # Manually init needed components only
    # Use simple engine for verification to avoid pool issues
    engine = create_async_engine("sqlite+aiosqlite:///./test_verify_v2.db")
    db = Database(engine=engine)
    repo = TaskRepository(db)
    
    await verify_media_group_with_repo(repo)

async def verify_media_group_with_repo(repo):
    print("\n=== Verifying Media Group Aggregation ===")
    
    group_id = "group_123"
    payloads = [
        {"chat_id": 1001, "message_id": 101, "grouped_id": group_id},
        {"chat_id": 1001, "message_id": 102, "grouped_id": group_id},
        {"chat_id": 1001, "message_id": 103, "grouped_id": group_id}
    ]
    
    for p in payloads:
        # Pushing directly to repo
        await repo.push("process_message", p)
        
    print("-> Pushed 3 group tasks to DB")
    
    # 2. Run Worker Fetch
    # We will simulate what WorkerService.start() does but effectively run one iteration
    
    task = await repo.fetch_next()
    if not task:
        print("FAIL: No task fetched")
        return
        
    print(f"-> Fetched Primary Task: {task.id} (GroupedID: {json.loads(task.task_data)['grouped_id']})")
    
    # Test fetch_group_tasks
    grouped_id = json.loads(task.task_data)['grouped_id']
    group_tasks = await repo.fetch_group_tasks(grouped_id, task.id)
    
    print(f"-> Fetched Related Group Tasks: {[t.id for t in group_tasks]}")
    
    if len(group_tasks) != 2:
        print("FAIL: Should have fetched 2 other tasks")
    else:
        print("PASS: Successfully aggregated 3 tasks total")
        
        # Cleanup
        await repo.complete(task.id)
        for t in group_tasks:
            await repo.complete(t.id)

async def main():
    # Initialize container (DB etc)
    # Patch config to use sqlite memory or local test db
    # AND handle broken .env file by moving it aside temporarily
    
    env_path = ".env"
    bak_path = ".env.verif_bak"
    has_moved = False
    
    try:
        # 1. 临时移除 .env 防止 pydantic-settings 解析错误
        if os.path.exists(env_path):
            try:
                os.rename(env_path, bak_path)
                has_moved = True
                print("-> Temporarily moved .env to .env.verif_bak")
            except Exception as e:
                print(f"WARN: Could not move .env: {e}")

        # 2. 设置必要的环境变量 (Mock)
        os.environ["API_ID"] = "12345"
        os.environ["API_HASH"] = "mock_hash"
        os.environ["BOT_TOKEN"] = "mock_token"
        os.environ["PHONE_NUMBER"] = "mock_phone"
        
        # 3. 导入核心模块 (现在 .env 不存在，应该使用默认值或环境变量)
        from core.config import settings
        settings.DATABASE_URL = "sqlite+aiosqlite:///./test_verify.db" 
        
        from models.models import Base
        from sqlalchemy.ext.asyncio import create_async_engine
        
        # Manually create tables without using models.get_engine/init_db
        # Use a fresh DB file to ensure schema is up to date
        init_engine = create_async_engine("sqlite+aiosqlite:///./test_verify_v2.db")
        async with init_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await init_engine.dispose()
        
        # NOTE: verify_media_group_with_repo uses the repo passed to it,
        # but verify_media_group creates its own DB connection.
        # We need to update verify_media_group to use the same DB file.
        await verify_media_group()
        
    finally:
        # 4. 恢复 .env
        if has_moved:
            try:
                if os.path.exists(bak_path):
                    os.rename(bak_path, env_path)
                    print("-> Restored .env")
            except Exception as e:
                print(f"CRITICAL: Failed to restore .env: {e} - Check {bak_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        traceback.print_exc()
