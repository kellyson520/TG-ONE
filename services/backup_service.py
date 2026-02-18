
import os
import logging
import shutil
import zipfile
import sqlite3
import glob
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Literal
from core.config import settings

logger = logging.getLogger(__name__)

class BackupService:
    """
    统一备份服务：管理项目内所有的代码与数据库备份。
    统一路径: data/backups/
    标准命名: tgone_{type}_{timestamp}.{ext}
    """
    def __init__(self):
        self.backup_dir = settings.BACKUP_DIR
        self.limit = settings.UPDATE_BACKUP_LIMIT
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _get_timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    async def backup_db(self, label: str = "manual") -> Optional[Path]:
        """
        备份数据库。使用 SQLite 备份 API 以确保事务安全性。
        命名格式: tgone_db_{timestamp}.bak
        """
        try:
            db_file = Path(settings.DB_PATH)
            if not db_file.is_absolute():
                db_file = settings.BASE_DIR / db_file
            
            if not db_file.exists():
                logger.warning(f"数据库文件不存在: {db_file}")
                return None

            timestamp = self._get_timestamp()
            backup_path = self.backup_dir / f"tgone_db_{timestamp}.bak"

            # 优先使用 SQLite 备份 API (支持在线备份)
            try:
                # 使用 loop.run_in_executor 处理同步的 sqlite 备份
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._sqlite_backup_sync, str(db_file), str(backup_path))
                logger.debug(f"通过 SQLite API 备份成功: {backup_path.name}")
            except Exception as e:
                logger.warning(f"SQLite 备份 API 失败: {e}，尝试直接文件拷贝...")
                shutil.copy2(db_file, backup_path)
            
            logger.info(f"✅ [备份] 数据库备份已创建: {backup_path.name}")
            self.rotate("tgone_db_*.bak")
            return backup_path
        except Exception as e:
            logger.error(f"❌ [备份] 数据库备份失败: {e}")
            return None

    def _sqlite_backup_sync(self, src_path: str, dst_path: str):
        """同步执行 sqlite 备份"""
        src_conn = sqlite3.connect(src_path)
        dst_conn = sqlite3.connect(dst_path)
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

    def backup_db_sync(self, label: str = "manual") -> Optional[Path]:
        """
        同步版本的数据库备份。适用于同步脚本或旧代码桥接。
        """
        try:
            db_file = Path(settings.DB_PATH)
            if not db_file.is_absolute():
                db_file = settings.BASE_DIR / db_file
            
            if not db_file.exists():
                logger.warning(f"数据库文件不存在: {db_file}")
                return None

            timestamp = self._get_timestamp()
            backup_path = self.backup_dir / f"tgone_db_{timestamp}.bak"

            try:
                self._sqlite_backup_sync(str(db_file), str(backup_path))
            except Exception as e:
                logger.warning(f"SQLite 备份 API 失败: {e}，尝试直接文件拷贝...")
                shutil.copy2(db_file, backup_path)
            
            logger.info(f"✅ [备份] 数据库同步备份已创建: {backup_path.name}")
            self.rotate("tgone_db_*.bak")
            return backup_path
        except Exception as e:
            logger.error(f"❌ [备份] 数据库同步备份失败: {e}")
            return None

    def backup_code_sync(self, label: str = "manual") -> Optional[Path]:
        """同步版本的代码备份"""
        try:
            timestamp = self._get_timestamp()
            backup_path = self.backup_dir / f"tgone_code_{timestamp}.zip"
            
            excluded_dirs = {
                ".git", "__pycache__", "venv", ".venv", ".mypy_cache",
                ".pytest_cache", "logs", "temp", "data", "sessions",
                "node_modules", "dist", ".agent"
            }
            excluded_exts = (".pyc", ".pyo", ".log", ".zip", ".tar.gz", ".bak")

            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as z:
                for root, dirs, files in os.walk(settings.BASE_DIR):
                    dirs[:] = [d for d in dirs if d not in excluded_dirs]
                    for file in files:
                        if file.endswith(excluded_exts):
                            continue
                        file_path = Path(root) / file
                        arcname = str(file_path.relative_to(settings.BASE_DIR))
                        z.write(file_path, arcname)
            
            logger.info(f"✅ [备份] 代码同步备份已创建: {backup_path.name}")
            self.rotate("tgone_code_*.zip")
            return backup_path
        except Exception as e:
            logger.error(f"❌ [备份] 代码同步备份失败: {e}")
            return None

    async def backup_code(self, label: str = "manual") -> Optional[Path]:
        """
        备份代码。压缩为 zip。
        命名格式: tgone_code_{timestamp}.zip
        """
        try:
            timestamp = self._get_timestamp()
            backup_path = self.backup_dir / f"tgone_code_{timestamp}.zip"
            
            excluded_dirs = {
                ".git", "__pycache__", "venv", ".venv", ".mypy_cache",
                ".pytest_cache", "logs", "temp", "data", "sessions",
                "node_modules", "dist", ".agent"
            }
            excluded_exts = (".pyc", ".pyo", ".log", ".zip", ".tar.gz", ".bak")

            def _zip_sync():
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for root, dirs, files in os.walk(settings.BASE_DIR):
                        dirs[:] = [d for d in dirs if d not in excluded_dirs]
                        for file in files:
                            if file.endswith(excluded_exts):
                                continue
                            file_path = Path(root) / file
                            arcname = str(file_path.relative_to(settings.BASE_DIR))
                            z.write(file_path, arcname)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _zip_sync)
            
            logger.info(f"✅ [备份] 代码备份已创建: {backup_path.name}")
            self.rotate("tgone_code_*.zip")
            return backup_path
        except Exception as e:
            logger.error(f"❌ [备份] 代码备份失败: {e}")
            return None

    def rotate(self, pattern: str):
        """旋转备份，保留最新的 limit 个"""
        try:
            # 搜索匹配的文件
            files = sorted(
                glob.glob(str(self.backup_dir / pattern)),
                key=os.path.getmtime,
                reverse=True
            )
            
            if len(files) > self.limit:
                to_delete = files[self.limit:]
                for f in to_delete:
                    try:
                        os.remove(f)
                        logger.debug(f"已清理旧备份: {os.path.basename(f)}")
                    except Exception as e:
                        logger.warning(f"删除物理文件失败: {f}, {e}")
        except Exception as e:
            logger.error(f"旋转备份失败: {e}")

    async def list_backups(self) -> List[Dict]:
        """
        列出所有标准化备份。
        支持: tgone_code_*, tgone_db_*, 以及兼容旧格式
        """
        patterns = [
            "tgone_code_*.zip",
            "tgone_db_*.bak",
            "tgone_backup_*.zip",
            "update_backup_*.zip",
            "*.bak"
        ]
        
        all_files = []
        for p in patterns:
            all_files.extend(glob.glob(str(self.backup_dir / p)))
            
        # 去重并排序
        unique_files = sorted(set(all_files), key=os.path.getmtime, reverse=True)
        
        results = []
        for f in unique_files:
            p = Path(f)
            stat = p.stat()
            
            # 识别类型
            if "_code_" in p.name or "update_backup" in p.name or "tgone_backup" in p.name:
                btype = "code"
            elif "_db_" in p.name or p.suffix == '.bak':
                btype = "db"
            else:
                btype = "unknown"
                
            # 提取日期
            try:
                # 尝试 YYYYMMDD_HHMMSS
                parts = p.stem.split("_")
                if len(parts) >= 2:
                    date_str = "_".join(parts[-2:])
                    dt = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                else:
                    raise ValueError()
            except:
                dt = datetime.fromtimestamp(stat.st_mtime)
                
            results.append({
                "name": p.name,
                "path": str(p),
                "type": btype,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": int(stat.st_mtime)
            })
            
        return results

    async def restore(self, backup_path: str) -> Tuple[bool, str]:
        """自动路由还原逻辑"""
        p = Path(backup_path)
        if not p.exists():
            return False, "文件不存在"
            
        if p.suffix == '.bak':
            return await self._restore_db(p)
        else:
            return await self._restore_code(p)

    async def _restore_db(self, path: Path) -> Tuple[bool, str]:
        """还原数据库"""
        try:
            db_file = Path(settings.DB_PATH)
            if not db_file.is_absolute():
                db_file = settings.BASE_DIR / db_file
            
            db_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 为安全起见，还原前再备份一份当前损坏/旧的 DB
            current_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(db_file, db_file.with_suffix(f".pre_restore_{current_tag}.bak"))
            
            shutil.copy2(path, db_file)
            return True, f"数据库已成功还原自 {path.name}"
        except Exception as e:
            return False, f"数据库还原失败: {e}"

    async def _restore_code(self, path: Path) -> Tuple[bool, str]:
        """还原代码"""
        try:
            def _extract_sync():
                with zipfile.ZipFile(path, 'r') as z:
                    for member in z.namelist():
                        if '..' in member or member.startswith('/') or '\\' in member:
                            continue
                        # 如果包含更新逻辑中的虚拟子目录，由于我们现在解压到根，需要小心
                        # 但新格式 tgone_code_*.zip 应该是扁平的根目录结构
                        target = settings.BASE_DIR / member
                        if member.endswith('/'):
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as src, open(target, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                                
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _extract_sync)
            return True, f"代码已成功还原自 {path.name}"
        except Exception as e:
            return False, f"代码还原失败: {e}"

# 单例
backup_service = BackupService()
