import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def backup_database(db_path: str, backup_dir: str) -> str:
    """Create a SQLite backup, falling back to file copy if the backup API fails."""
    source = Path(db_path)
    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        return ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = target_dir / f"{source.stem}_{timestamp}.bak"

    try:
        src_conn = sqlite3.connect(str(source))
        dst_conn = sqlite3.connect(str(target))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
    except Exception:
        shutil.copy2(source, target)

    return str(target)


def rotate_backups(backup_dir: str, retention_count: int = 5) -> None:
    target_dir = Path(backup_dir)
    if retention_count < 0 or not target_dir.exists():
        return

    backups = [
        path for path in target_dir.iterdir()
        if path.is_file() and path.name.endswith(".bak")
    ]
    backups.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    for stale in backups[retention_count:]:
        try:
            os.remove(stale)
        except FileNotFoundError:
            pass
