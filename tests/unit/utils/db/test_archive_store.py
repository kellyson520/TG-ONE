
import os
import pytest
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch

import duckdb
from repositories import archive_store

# Check if DuckDB is mocked by conftest.py
IS_DUCKDB_MOCKED = isinstance(duckdb, MagicMock) or hasattr(duckdb, 'DEFAULT_REPOSITORY') # MagicMock traits

def create_dummy_rows(count: int) -> List[Dict[str, Any]]:
    rows = []
    base_time = datetime.utcnow()
    for i in range(count):
        rows.append({
            "id": i,
            "name": f"item_{i}",
            "value": i * 1.5,
            "created_at": (base_time - timedelta(minutes=i)).isoformat(),
            "active": i % 2 == 0
        })
    return rows

@pytest.fixture
def temp_archive_root(tmp_path):
    """Setup a temporary directory for archive root"""
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    
    # Patch the ARCHIVE_ROOT in the module
    original_root = archive_store.ARCHIVE_ROOT
    archive_store.ARCHIVE_ROOT = str(archive_dir)
    
    yield str(archive_dir)
    
    # Restore
    archive_store.ARCHIVE_ROOT = original_root

class TestArchiveStore:

    def test_write_parquet_basic(self, temp_archive_root):
        """Test basic writing of rows to parquet"""
        rows = create_dummy_rows(100)
        table_name = "test_table"
        
        if IS_DUCKDB_MOCKED:
            # Smart mock for os.path.exists
            original_exists = os.path.exists
            def side_effect(path):
                # Simulate that the parquet file exists (created by "DuckDB")
                if str(path).endswith(".parquet"):
                    return True
                return original_exists(path)

            with patch('os.path.exists', side_effect=side_effect), \
                 patch('os.replace'), \
                 patch('glob.glob', return_value=['fake.parquet']):
                
                out_dir = archive_store.write_parquet(table_name, rows)
                # It should return a directory path
                assert out_dir != ""
                assert "test_table" in out_dir
        else:
            # Real DuckDB
            out_dir = archive_store.write_parquet(table_name, rows)
            assert out_dir != ""
            assert os.path.exists(out_dir)
            parquet_files = glob.glob(os.path.join(out_dir, "*.parquet"))
            assert len(parquet_files) >= 1

    def test_query_parquet_duckdb(self, temp_archive_root):
        """Test querying the archive"""
        if IS_DUCKDB_MOCKED:
             # Patch glob to return some fake files
             with patch('glob.glob', return_value=['/fake/path.parquet']):
                 # Patch duckdb connection to return dummy data
                 con = duckdb.connect()
                 # We need fetchall to return list of tuples
                 con.execute.return_value.description = [('id', 'int'), ('name', 'str')] # Mock description
                 con.execute.return_value.fetchall.return_value = [(1, "item_1")]
                 
                 result = archive_store.query_parquet_duckdb("test_table", "1=1", [])
                 assert len(result) == 1
                 assert result[0]['id'] == 1
        else:
            rows = create_dummy_rows(50)
            table_name = "query_table"
            archive_store.write_parquet(table_name, rows)
            result = archive_store.query_parquet_duckdb(table_name, "1=1", [])
            assert len(result) == 50

    def test_compact_small_files(self, temp_archive_root):
        """Test compacting small files"""
        if IS_DUCKDB_MOCKED:
            pass # Skip complex mock logic for now
        else:
            table_name = "compact_table"
            rows = create_dummy_rows(10)
            fixed_dt = datetime.utcnow()
            for i in range(5):
                 archive_store.write_parquet(table_name, rows, partition_dt=fixed_dt)
            
            results = archive_store.compact_small_files(table_name, min_files=2)
            assert len(results) > 0
            
            partition_dir = archive_store._partition_path(table_name, fixed_dt)
            compact_files = glob.glob(os.path.join(partition_dir, "compact-*.parquet"))
            assert len(compact_files) >= 1

    def test_write_chunking(self, temp_archive_root):
        """Test that large datasets are chunked"""
        if IS_DUCKDB_MOCKED:
            pass
        else:
            rows = create_dummy_rows(120)  # Total > 50*2
            table_name = "chunk_table"
            with patch.dict(os.environ, {"ARCHIVE_WRITE_CHUNK_SIZE": "50"}):
                out_dir = archive_store.write_parquet(table_name, rows)
                parquet_files = glob.glob(os.path.join(out_dir, "*.parquet"))
                assert len(parquet_files) >= 3

class TestArchiveErrorRecovery:
    
    def test_write_io_error_cleanup(self, temp_archive_root):
        """Test that temporary files are cleaned up if writing fails"""
        rows = create_dummy_rows(10)
        table_name = "error_table"
        
        # Determine the expected tmp file path
        # We need to spy on the internal logic or predict the path.
        # Since the filename includes timestamp/pid, it's hard to predict exactly.
        # But we can check if ANY .tmp file exists in the directory after failure.
        
        partition_path = archive_store._partition_path(table_name, datetime.utcnow())
        
        # We need to mock DuckDB to simulate failure AFTER creating a file
        if IS_DUCKDB_MOCKED:
             with patch('duckdb.connect') as mock_connect:
                mock_con = MagicMock()
                mock_connect.return_value = mock_con
                
                def side_effect_execute(*args, **kwargs):
                    # Simulate creating the .tmp file
                    # We can find the .tmp file path from the args if it's the COPY command
                    cmd = args[0]
                    if "COPY" in cmd and "TO '" in cmd:
                        # Extract path from cmd
                        # COPY ... TO 'path' ...
                        try:
                            start = cmd.index("TO '") + 4
                            end = cmd.index("'", start)
                            file_path = cmd[start:end]
                            
                            # Ensure dir exists
                            dirname = os.path.dirname(file_path)
                            if not os.path.exists(dirname):
                                os.makedirs(dirname)
                                
                            with open(file_path, "w") as f:
                                f.write("partial data")
                        except Exception:
                            # Fallback if parsing fails (shouldn't happen with correct SQL)
                            pass
                        
                        raise IOError("Simulated Disk Full")
                    return MagicMock()
                
                mock_con.execute.side_effect = side_effect_execute
                
                with pytest.raises(IOError, match="Simulated Disk Full"):
                    archive_store.write_parquet(table_name, rows)
                
                # Assert that the file was cleaned up
                # Note: Currently archive_store.py DOES NOT wrap the execute in a try/except to clean up 
                # tmp files if execute fails. So this test expects failure (or reveals the bug).
                # The task is to "Verify temporary file cleanup". 
                # If this assertion fails, we need to fix the code.
                
                tmp_files = glob.glob(os.path.join(partition_path, "*.tmp"))
                assert len(tmp_files) == 0, "Temporary files should be cleaned up on error"

