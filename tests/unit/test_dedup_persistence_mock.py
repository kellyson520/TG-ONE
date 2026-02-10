
import asyncio
from unittest.mock import MagicMock, AsyncMock
from repositories.dedup_repo import DedupRepository
from models.system import SystemConfiguration
import json

async def test_persistence():
    # Mock DB Session
    mock_session = AsyncMock()
    mock_db = MagicMock()
    mock_db.session.return_value = mock_session
    mock_session.__aenter__.return_value = mock_session
    
    repo = DedupRepository(mock_db)
    
    # Test save_config
    config = {"enable_dedup": True, "threshold": 0.88}
    
    # Mock execute for check existing (return None first time)
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result_empty
    
    await repo.save_config(config)
    
    # Verify add was called
    print(f"Session.add called count: {mock_session.add.call_count}")
    args = mock_session.add.call_args[0][0]
    print(f"Saved Object: key={args.key}, value={args.value}")
    
    assert args.key == "dedup_global_config"
    assert json.loads(args.value) == config
    
    # Test load_config
    # Mock result with data
    mock_obj = SystemConfiguration(key="dedup_global_config", value=json.dumps(config))
    mock_result_data = MagicMock()
    mock_result_data.scalar_one_or_none.return_value = mock_obj
    mock_session.execute.return_value = mock_result_data
    
    loaded = await repo.load_config()
    print(f"Loaded config: {loaded}")
    
    assert loaded == config
    print("Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_persistence())
