
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from scheduler.db_archive_job import archive_once
from models.models import MediaSignature, ErrorLog
from sqlalchemy import select, func

@pytest.mark.asyncio
async def test_archive_recovery_on_failure(db, monkeypatch):
    """验证归档失败时不会从 SQLite 删除数据 (数据不丢失验证)"""
    import os
    # 设置测试数据库路径，确保 get_engine() 能拿到有效的 URL
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("DEDUP_DATABASE_URL", "sqlite:///test.db")
    
    # 1. 准备过期数据
    cutoff = datetime.utcnow() - timedelta(days=100)
    for i in range(10):
        sig = MediaSignature(
            chat_id=12345,
            signature=f"sig_{i}",
            file_id=f"file_{i}",
            content_hash=f"hash_{i}",
            created_at=cutoff,
            last_seen=cutoff
        )
        db.add(sig)
    
    # 2. 准备错误日志
    for i in range(5):
        err = ErrorLog(
            level="ERROR",
            module="test",
            message=f"error_{i}",
            created_at=cutoff
        )
        db.add(err)
    
    await db.commit()
    
    # 3. Mock write_parquet 抛出异常 + Mock bloom_index 以免报错
    with patch("scheduler.db_archive_job.write_parquet", side_effect=OSError("Disk Full")), \
         patch("utils.db.bloom_index.bloom.add_batch", return_value=None):
        # 执行归档
        archive_once()
        
    # 4. 验证数据是否还在 SQLite
    # 注意：我们必须等待异步 session 提交，archive_once 内部开启的是同步 session。
    # 在内存或测试库中，如果配置正确，它们应该看到同一批数据。
    from models.models import get_session
    with get_session() as session:
        from sqlalchemy import func
        sig_count = session.query(func.count(MediaSignature.id)).scalar()
        err_count = session.query(func.count(ErrorLog.id)).scalar()
        
        # 预期：数据不应该被删除，因为归档动作抛出了异常
        print(f"DEBUG: sig_count={sig_count}, err_count={err_count}")
        assert sig_count == 10
        assert err_count == 5
