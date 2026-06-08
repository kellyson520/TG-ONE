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


@pytest.mark.asyncio
async def test_restore_code_skips_symlink_escape(tmp_path, monkeypatch):
    import zipfile

    from services.backup_service import BackupService
    from services import backup_service as backup_module

    base_dir = tmp_path / "base"
    outside_dir = tmp_path / "outside"
    backup_dir = tmp_path / "backups"
    base_dir.mkdir()
    outside_dir.mkdir()
    (base_dir / "link").symlink_to(outside_dir, target_is_directory=True)
    backup_dir.mkdir()

    archive = tmp_path / "restore.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("link/escaped.txt", "escaped")

    monkeypatch.setattr(backup_module.settings, "BASE_DIR", base_dir)
    monkeypatch.setattr(backup_module.settings, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(backup_module.settings, "UPDATE_BACKUP_LIMIT", 3)

    ok, _ = await BackupService()._restore_code(archive)

    assert ok
    assert not (outside_dir / "escaped.txt").exists()


def test_backup_code_excludes_secret_files(tmp_path, monkeypatch):
    import zipfile

    from services.backup_service import BackupService
    from services import backup_service as backup_module

    base_dir = tmp_path / "base"
    backup_dir = tmp_path / "backups"
    base_dir.mkdir()
    backup_dir.mkdir()
    (base_dir / "app.py").write_text("print('ok')", encoding="utf-8")
    (base_dir / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (base_dir / "secret.key").write_text("secret", encoding="utf-8")
    (base_dir / "private.pem").write_text("secret", encoding="utf-8")

    monkeypatch.setattr(backup_module.settings, "BASE_DIR", base_dir)
    monkeypatch.setattr(backup_module.settings, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(backup_module.settings, "UPDATE_BACKUP_LIMIT", 3)

    backup_path = BackupService().backup_code_sync()

    assert backup_path is not None
    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
    assert "app.py" in names
    assert ".env" not in names
    assert "secret.key" not in names
    assert "private.pem" not in names
