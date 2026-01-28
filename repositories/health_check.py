import sqlite3
import shutil
import os
import time
import logging
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)

class DatabaseHealthManager:
    """
    Manage SQLite database health including integrity checks and auto-repair.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.backup_path = self.db_path.with_suffix('.db.bak')
    
    def check_health(self) -> bool:
        """
        Check database integrity.
        Returns True if healthy, False if malformed.
        """
        if not self.db_path.exists():
            logger.info(f"Database {self.db_path} does not exist. Skipping health check.")
            return True
            
        logger.info(f"Checking integrity of {self.db_path}...")
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                if row[0] != "ok":
                    logger.error(f"CORRUPTION DETECTED in {self.db_path}: {row[0]}")
                    return False
            
            logger.info(f"Database {self.db_path} is healthy.")
            return True
        except sqlite3.DatabaseError as e:
            logger.critical(f"Database integrity check failed with critical error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during health check: {e}")
            return False

    def heal(self) -> bool:
        """
        Attempt to repair the database using VACUUM INTO strategy.
        This operation will replace the database file.
        """
        if not self.db_path.exists():
            return False
            
        logger.warning(f"Starting emergency repair for {self.db_path}...")
        
        timestamp = int(time.time())
        corrupted_backup = self.db_path.with_name(f"{self.db_path.stem}_corrupted_{timestamp}.bak")
        rebuilt_path = self.db_path.with_name(f"{self.db_path.stem}_rebuilt_{timestamp}.db")
        
        # 1. Backup corrupted file
        try:
            logger.info(f"Backing up corrupted database to {corrupted_backup}")
            shutil.copy2(self.db_path, corrupted_backup)
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

        # 2. Rebuild using VACUUM
        try:
            conn = sqlite3.connect(str(self.db_path))
            # Try VACUUM INTO first (safer)
            try:
                conn.execute(f"VACUUM INTO '{rebuilt_path}'")
                logger.info(f"VACUUM INTO successful: {rebuilt_path}")
            except Exception as vacuum_into_err:
                logger.warning(f"VACUUM INTO failed ({vacuum_into_err}), attempting in-place VACUUM...")
                # Fallback to standard VACUUM
                conn.execute("VACUUM;")
                logger.info("Standard VACUUM successful.")
                rebuilt_path = None # In-place repair
                
            conn.close()
        except Exception as e:
            logger.critical(f"Database repair failed during VACUUM: {e}")
            return False

        # 3. Swap files if we used VACUUM INTO
        if rebuilt_path and rebuilt_path.exists():
            logger.info(f"Swapping {self.db_path} with rebuilt version...")
            try:
                # On Windows, replace might fail if file is open.
                # In a startup hook, it should be fine as no one else is connected yet.
                os.replace(rebuilt_path, self.db_path)
                logger.info("Database file replaced successfully.")
            except Exception as e:
                logger.critical(f"Failed to replace database file: {e}")
                return False
        
        # 4. Verify repair
        if self.check_health():
            logger.info("Database repair verification passed.")
            return True
        else:
            logger.critical("Database is still malformed after repair attempt.")
            return False

def check_and_fix_dbs_at_startup():
    """
    Main entry point for startup checks.
    Checks configured databases and attempts repair if configured.
    """
    if not settings.ENABLE_DB_HEALTH_CHECK:
        return

    # Extract DB path from URL (Assuming SQLite)
    db_url = settings.DATABASE_URL
    if not db_url.startswith("sqlite"):
        logger.info("Health check skipped: Non-SQLite database.")
        return

    # Parse path from url "sqlite+aiosqlite:///db/forward.db"
    # Basic parsing
    path_str = db_url.split("///")[-1]
    # Handle absolute paths if needed, but relative usually works
    db_path = Path(settings.BASE_DIR) / path_str
    
    # Also check dedup.db if it exists in the same dir
    dedup_path = db_path.parent / "dedup.db"
    
    targets = [db_path]
    if dedup_path.exists():
        targets.append(dedup_path)
        
    for target in targets:
        manager = DatabaseHealthManager(str(target))
        if not manager.check_health():
            if settings.ENABLE_DB_AUTO_REPAIR:
                success = manager.heal()
                if not success:
                    logger.critical(f"Automated repair FAILED for {target}. Manual intervention required.")
                    # Depending on policy, might want to exit here.
            else:
                logger.critical(f"Database {target} is corrupted and auto-repair is DISABLED.")
