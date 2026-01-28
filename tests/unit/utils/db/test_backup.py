
import os
import sqlite3
from repositories import backup
from unittest.mock import patch

def create_dummy_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO test (value) VALUES ('foo')")
    conn.commit()
    conn.close()

class TestBackup:

    def test_backup_success_sqlite_api(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        backup_dir = str(tmp_path / "backups")
        
        create_dummy_db(db_path)
        
        path = backup.backup_database(db_path, backup_dir)
        
        assert path != ""
        assert os.path.exists(path)
        assert path.endswith(".bak")
        
        # Verify content
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT value FROM test")
        assert cur.fetchone()[0] == 'foo'
        conn.close()

    def test_backup_fallback_copy(self, tmp_path):
        db_path = str(tmp_path / "test_copy.db")
        backup_dir = str(tmp_path / "backups_copy")
        create_dummy_db(db_path)
        
        # Patch sqlite3.connect to fail ONLY for backup
        # But we need it for create_dummy_db? No, that calls real sqlite3.
        # We patch inside the module backup.sqlite3
        
        with patch('repositories.backup.sqlite3.connect', side_effect=Exception("API Error")):
             path = backup.backup_database(db_path, backup_dir)
             
        assert path != ""
        assert os.path.exists(path)
        # Should contain data (copied)
        # We can't use sqlite3 to check since we mocked it?
        # No, we mocked repositories.backup.sqlite3.
        # We can use real sqlite3 here.
        real_conn = sqlite3.connect(path)
        cur = real_conn.execute("SELECT value FROM test")
        assert cur.fetchone()[0] == 'foo'
        real_conn.close()

    def test_rotate_backups(self, tmp_path):
        backup_dir = str(tmp_path / "rotate")
        os.makedirs(backup_dir)
        
        # Create 10 files
        for i in range(10):
            p = os.path.join(backup_dir, f"backup_{i}.bak")
            with open(p, "w") as f:
                f.write("data")
            # Ensure different mtimes
            os.utime(p, (i*100, i*100))
            
        backup.rotate_backups(backup_dir, retention_count=5)
        
        files = os.listdir(backup_dir)
        assert len(files) == 5
        # Should keep 5, 6, 7, 8, 9 (highest mtime)
        assert "backup_9.bak" in files
        assert "backup_0.bak" not in files
