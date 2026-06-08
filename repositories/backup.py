import logging
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
        with closing(sqlite3.connect(str(source))) as src_conn:
            with closing(sqlite3.connect(str(target))) as dst_conn:
                with dst_conn:
                    src_conn.backup(dst_conn)
    except Exception:
        logger.warning("SQLite 备份失败，降级为文件复制: source=%s target=%s", source, target, exc_info=True)
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
            logger.debug("过期备份文件已不存在，跳过删除: path=%s", stale)
