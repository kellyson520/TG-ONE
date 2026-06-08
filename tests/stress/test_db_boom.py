
import os
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import duckdb
import glob
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from models.models import Base, MediaSignature, ErrorLog
from scheduler import db_archive_job
from repositories.archive_manager import ArchiveManager

pytestmark = pytest.mark.stress

IS_DUCKDB_MOCKED = isinstance(duckdb, MagicMock) or hasattr(duckdb, 'DEFAULT_REPOSITORY')

# Helper to generate random string
def random_str(length=10):
    return uuid.uuid4().hex[:length]

@pytest.fixture(scope="module")
def boom_db_engine(tmp_path_factory):
    """Create a temporary file-based SQLite database for boom testing"""
    temp_dir = tmp_path_factory.mktemp("boom_db")
    db_path = temp_dir / "boom.db"
    db_url = f"sqlite:///{db_path}"
    
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    yield engine, str(db_path)
    
    engine.dispose()

@pytest.fixture
def boom_session(boom_db_engine):
    engine, _ = boom_db_engine
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def temp_archive_env_stress(tmp_path):
    archive_dir = tmp_path / "stress_archive"
    bloom_dir = tmp_path / "stress_bloom"
    archive_dir.mkdir()
    bloom_dir.mkdir()

    original_archive_checked = db_archive_job._archive_system_checked

    import repositories.archive_store as archive_store
    import repositories.archive_init as archive_init
    import repositories.bloom_index as bloom_index

    original_store_root = archive_store.ARCHIVE_ROOT
    original_init_archive_root = archive_init.ARCHIVE_ROOT
    original_init_bloom_root = archive_init.BLOOM_ROOT
    original_bloom_root = bloom_index.BLOOM_ROOT

    archive_store.ARCHIVE_ROOT = str(archive_dir)
    archive_init.ARCHIVE_ROOT = str(archive_dir)
    archive_init.BLOOM_ROOT = str(bloom_dir)
    bloom_index.BLOOM_ROOT = str(bloom_dir)
    db_archive_job._archive_system_checked = False

    try:
        yield {
            "archive_dir": archive_dir,
            "bloom_dir": bloom_dir,
        }
    finally:
        archive_store.ARCHIVE_ROOT = original_store_root
        archive_init.ARCHIVE_ROOT = original_init_archive_root
        archive_init.BLOOM_ROOT = original_init_bloom_root
        bloom_index.BLOOM_ROOT = original_bloom_root
        db_archive_job._archive_system_checked = original_archive_checked

class TestDBBoom:
    
    def populate_db(self, session, count=1000):
        """Bulk insert data"""
        sigs = []
        logs = []
        
        # Insert MediaSignatures (old)
        old_date = (datetime.utcnow() - timedelta(days=100)).isoformat()
        for i in range(count):
            sigs.append(MediaSignature(
                chat_id=f"chat_{i%10}",
                signature=f"sig_{i}",
                content_hash=random_str(),
                created_at=old_date,
                updated_at=old_date,
                last_seen=old_date,
                count=1,
                media_type="photo"
            ))
            
            logs.append(ErrorLog(
                level="ERROR",
                module="test_module",
                message=f"Boom error {i}",
                created_at=old_date
            ))
            
        session.bulk_save_objects(sigs)
        session.bulk_save_objects(logs)
        session.commit()

    def test_archive_force_boom(self, boom_db_engine, boom_session, temp_archive_env_stress):
        """
        Populate DB with significant data -> Force Archive -> Verify Vacuum
        """
        engine, db_path = boom_db_engine
        
        # 1. Populate
        ROW_COUNT = 5000  # Adjust for speed vs stress
        print(f"\n[BOOM] Generating {ROW_COUNT} rows...")
        self.populate_db(boom_session, ROW_COUNT)
        
        # Check size before
        size_before = os.path.getsize(db_path)
        print(f"[BOOM] DB Size Before: {size_before / 1024 / 1024:.2f} MB")
        
        # 2. Setup Patches
        class MockSessionCtx:
            def __init__(self, sess): self.sess = sess
            def __enter__(self): return self.sess
            def __exit__(self, exc_type, exc_val, exc_tb): pass

        mock_get_session = MagicMock(return_value=MockSessionCtx(boom_session))
        mock_get_engine = MagicMock(return_value=engine)
        
        async_engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            future=True,
        )
        async_session_factory = async_sessionmaker(
            async_engine,
            expire_on_commit=False,
        )
        manager = ArchiveManager(async_session_factory)

        write_parquet_patch = (
            patch('scheduler.db_archive_job.write_parquet', return_value="/fake/path")
            if IS_DUCKDB_MOCKED
            else patch('scheduler.db_archive_job.write_parquet', wraps=db_archive_job.write_parquet)
        )

        with patch('scheduler.db_archive_job.get_session', mock_get_session), \
             patch('scheduler.db_archive_job.get_dedup_session', mock_get_session), \
             patch('models.models.get_engine', mock_get_engine), \
             patch('scheduler.db_archive_job.get_archive_manager', return_value=manager), \
             patch('scheduler.db_archive_job.analyze_database'), \
             patch('scheduler.db_archive_job.vacuum_database') as mock_vacuum, \
             write_parquet_patch:
            
            def real_vacuum_side_effect():
                with engine.connect() as conn:
                    conn.execute(text("VACUUM"))
            
            mock_vacuum.side_effect = real_vacuum_side_effect
            
            # 3. Run Force Archive
            print("[BOOM] Running archive_force()...")
            start_time = time.time()
            db_archive_job.archive_force()
            duration = time.time() - start_time
            print(f"[BOOM] Archive finished in {duration:.2f}s")
            
        # 4. Verify DB Empty (of archived data)
        count_sigs = boom_session.query(MediaSignature).count()
        count_logs = boom_session.query(ErrorLog).count()
        assert count_sigs == 0, f"Expected 0 signatures, found {count_sigs}"
        assert count_logs == 0, f"Expected 0 logs, found {count_logs}"
        
        # 5. Check Parquet Files (Only if real)
        if not IS_DUCKDB_MOCKED:
            media_files = glob.glob(os.path.join(temp_archive_env_stress["archive_dir"], "media_signatures", "**", "*.parquet"), recursive=True)
            assert len(media_files) > 0
        else:
            print("[BOOM] Skipping Parquet check due to Mock DuckDB")
        
        # 6. Check Size After
        size_after = os.path.getsize(db_path)
        print(f"[BOOM] DB Size After: {size_after / 1024 / 1024:.2f} MB")
        
        # With VACUUM, size should decrease significantly
        assert size_after < size_before, "Expected DB size to decrease after VACUUM"
        import asyncio
        asyncio.run(async_engine.dispose())
