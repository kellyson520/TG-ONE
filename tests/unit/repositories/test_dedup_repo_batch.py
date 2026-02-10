
import pytest
from unittest.mock import MagicMock, AsyncMock
from repositories.dedup_repo import DedupRepository

@pytest.mark.asyncio
class TestDedupRepoBatch:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        session = AsyncMock()
        db.session.return_value.__aenter__.return_value = session
        return db, session

    async def test_batch_add_media_signatures_filtering(self, mock_db):
        db, session = mock_db
        repo = DedupRepository(db)
        
        # 准备带有多余字段的数据
        records = [
            {
                "chat_id": "1001",
                "signature": "sig1",
                "extra_field": "should_be_filtered"
            }
        ]
        
        # 模拟 run_sync
        session.run_sync = AsyncMock()
        
        result = await repo.batch_add_media_signatures(records)
        
        assert result is True
        # 验证 run_sync 被调用且传入了过滤后的数据
        # 注意: run_sync 的第一个参数是 lambda
        call_args = session.run_sync.call_args
        assert call_args is not None
        
        # 验证提交
        session.commit.assert_awaited_once()

    async def test_batch_add_media_signatures_empty(self, mock_db):
        db, session = mock_db
        repo = DedupRepository(db)
        
        result = await repo.batch_add_media_signatures([])
        assert result is True
        session.run_sync.assert_not_called()
