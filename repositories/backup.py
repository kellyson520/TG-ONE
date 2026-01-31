
import os
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)

def backup_database(db_path: str = None, backup_dir: str = None) -> str:
    """
    Backup the SQLite database.
    Uses SQLite Online Backup API if available, or file copy as fallback.
    """
    if db_path is None:
        # Infer from settings (assuming standard structure)
        # settings.DATABASE_URL usually 'sqlite+aiosqlite:///./config/db/bot.db'
        # extracting path...
        if settings.DATABASE_URL.startswith("sqlite"):
            path_str = settings.DATABASE_URL.split("///")[-1]
            db_path = str(Path(path_str).resolve())
        else:
            logger.error("Only SQLite backup is supported currently.")
            return ""

    if backup_dir is None:
        backup_dir = settings.BACKUP_DIR

    if not os.path.exists(db_path):
        logger.error(f"Database file not found at: {db_path}")
        return ""

    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(db_path)
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
    
    logger.info(f"Starting backup of {db_path} to {backup_path}")
    
    try:
        # Try Online Backup API (safest)
        # Open source connection
        src = sqlite3.connect(db_path)
        # Open dest connection
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        logger.info("Backup successful via SQLite API")
    except Exception as e:
        logger.warning(f"SQLite Backup API failed: {e}. Falling back to file copy.")
        try:
            shutil.copy2(db_path, backup_path)
            logger.info("Backup successful via file copy")
        except Exception as copy_e:
            logger.error(f"Backup failed completely: {copy_e}")
            return ""

    return backup_path

def rotate_backups(backup_dir: str = None, retention_count: int = 5):
    """Keep only the latest N backups"""
    if backup_dir is None:
        backup_dir = str(settings.BACKUP_DIR)
        
    try:
        if not os.path.exists(backup_dir):
            return
            
        files = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".bak")],
            key=os.path.getmtime
        )
        
        if len(files) > retention_count:
            to_remove = files[:-retention_count]
            for f in to_remove:
                logger.info(f"Removing old backup: {f}")
                os.remove(f)
                
    except Exception as e:
        logger.error(f"Error rotating backups: {e}")
