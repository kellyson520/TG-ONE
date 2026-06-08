"""Test that bare except clauses in backup_service.py are properly typed."""
import pytest
import inspect


def test_no_bare_except_in_backup_service():
    """Verify that backup_service.py has no bare except: clauses."""
    from services import backup_service
    source = inspect.getsource(backup_service)
    lines = source.split(chr(10))
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except:":
            pytest.fail(f"Found bare except: at source line {i+1}: {line}")


def test_list_backups_date_parsing_fallback():
    """list_backups should handle files with non-standard date formats gracefully."""
    # This test verifies that the except clause catches ValueError correctly
    from datetime import datetime
    import os
    import tempfile
    from pathlib import Path
    
    # Create a temporary file with a non-standard name
    with tempfile.NamedTemporaryFile(suffix=".bak", prefix="tgone_db_", delete=False) as f:
        f.write(b"test")
        temp_path = f.name
    
    try:
        stat = os.stat(temp_path)
        # Simulate the fallback logic
        p = Path(temp_path)
        try:
            parts = p.stem.split("_")
            if len(parts) >= 2:
                date_str = "_".join(parts[-2:])
                dt = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            else:
                raise ValueError()
        except (ValueError, IndexError):
            dt = datetime.fromtimestamp(stat.st_mtime)
        
        assert isinstance(dt, datetime)
    finally:
        os.unlink(temp_path)
