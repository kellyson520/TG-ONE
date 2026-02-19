
import logging
from typing import Optional
from services.backup_service import backup_service

logger = logging.getLogger(__name__)

def backup_database(db_path=None, backup_dir=None) -> Optional[str]:
    """
    [Legacy Bridge] 备份数据库。转发至 BackupService 同步方法。
    参数由 models.models.backup_database 传递，但 BackupService 会自动管理路径。
    """
    path = backup_service.backup_db_sync()
    return str(path) if path else None

def rotate_backups():
    """
    [Legacy Bridge] 旋转备份。转发至 BackupService。
    """
    backup_service.rotate("tgone_db_*.bak")
    backup_service.rotate("*.bak")
