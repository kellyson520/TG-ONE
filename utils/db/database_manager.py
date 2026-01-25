"""
数据库权限管理器
修复SQLite数据库只读权限问题
"""

import shutil
import sqlite3
import stat

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库权限管理器"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.session_dir = self.project_root / "sessions"
        self.db_dir = self.project_root / "db"
        # 备份目录仅用于存放备份文件，必须从扫描与写入测试中排除
        self.backup_dir = self.project_root / "backups"

    def check_directory_permissions(self, directory: Path) -> Dict[str, bool]:
        """检查目录权限"""
        result = {
            "exists": False,
            "readable": False,
            "writable": False,
            "executable": False,
        }

        try:
            if directory.exists():
                result["exists"] = True
                result["readable"] = os.access(directory, os.R_OK)
                result["writable"] = os.access(directory, os.W_OK)
                result["executable"] = os.access(directory, os.X_OK)

        except Exception as e:
            logger.error(f"检查目录权限失败 {directory}: {e}")

        return result

    def check_file_permissions(self, file_path: Path) -> Dict[str, bool]:
        """检查文件权限"""
        result = {
            "exists": False,
            "readable": False,
            "writable": False,
            "size": 0,
            "locked": False,
        }

        try:
            if file_path.exists():
                result["exists"] = True
                result["readable"] = os.access(file_path, os.R_OK)
                result["writable"] = os.access(file_path, os.W_OK)
                result["size"] = file_path.stat().st_size

                # 检查文件是否被锁定
                try:
                    with open(file_path, "a"):
                        pass
                except (PermissionError, IOError):
                    result["locked"] = True

        except Exception as e:
            logger.error(f"检查文件权限失败 {file_path}: {e}")

        return result

    def fix_directory_permissions(self, directory: Path) -> bool:
        """修复目录权限"""
        try:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建目录: {directory}")

            # 设置目录权限为可读写执行
            if os.name == "posix":  # Unix/Linux/macOS
                directory.chmod(0o755)
            elif os.name == "nt":  # Windows
                # Windows权限设置
                try:
                    import subprocess

                    # 给当前用户完全控制权限
                    subprocess.run(
                        [
                            "icacls",
                            str(directory),
                            "/grant",
                            f'{os.getenv("USERNAME")}:F',
                            "/t",
                        ],
                        capture_output=True,
                        check=False,
                    )
                except Exception:
                    pass  # 如果icacls失败，继续尝试其他方法

            logger.info(f"修复目录权限: {directory}")
            return True

        except Exception as e:
            logger.error(f"修复目录权限失败 {directory}: {e}")
            return False

    def fix_file_permissions(self, file_path: Path) -> bool:
        """修复文件权限"""
        try:
            if not file_path.exists():
                # 创建空文件
                file_path.touch()
                logger.info(f"创建文件: {file_path}")

            # 设置文件权限为可读写
            if os.name == "posix":  # Unix/Linux/macOS
                file_path.chmod(0o644)
            elif os.name == "nt":  # Windows
                # Windows权限设置
                try:
                    import subprocess

                    # 给当前用户完全控制权限
                    subprocess.run(
                        [
                            "icacls",
                            str(file_path),
                            "/grant",
                            f'{os.getenv("USERNAME")}:F',
                        ],
                        capture_output=True,
                        check=False,
                    )
                except Exception:
                    pass  # 如果icacls失败，继续尝试其他方法

            logger.info(f"修复文件权限: {file_path}")
            return True

        except Exception as e:
            logger.error(f"修复文件权限失败 {file_path}: {e}")
            return False

    def test_database_write(self, db_path: Path) -> bool:
        """测试数据库是否可写"""
        try:
            # 如果数据库不存在，创建一个空的
            if not db_path.exists():
                db_path.touch()

            # 尝试连接并写入
            with sqlite3.connect(str(db_path), timeout=30.0) as conn:
                try:
                    conn.execute("PRAGMA busy_timeout=30000")
                    conn.execute("PRAGMA foreign_keys=ON")
                except Exception:
                    pass
                conn.execute("CREATE TABLE IF NOT EXISTS test_write (id INTEGER)")
                conn.execute("INSERT OR REPLACE INTO test_write (id) VALUES (1)")
                conn.commit()

                # 清理测试表
                conn.execute("DROP TABLE IF EXISTS test_write")
                conn.commit()

            logger.debug(f"数据库写入测试通过: {db_path}")
            return True

        except sqlite3.OperationalError as e:
            if "readonly database" in str(e).lower():
                logger.error(f"数据库只读: {db_path}")
                return False
            elif "locked" in str(e).lower():
                logger.error(f"数据库被锁定: {db_path}")
                return False
            else:
                logger.error(f"数据库操作错误 {db_path}: {e}")
                return False
        except Exception as e:
            logger.error(f"数据库写入测试失败 {db_path}: {e}")
            return False

    def backup_database(self, db_path: Path) -> Optional[Path]:
        """备份数据库"""
        try:
            if not db_path.exists():
                return None

            timestamp = int(time.time())
            backup_name = f"{db_path.stem}.backup.{timestamp}{db_path.suffix}"
            backup_path = db_path.parent / backup_name

            shutil.copy2(db_path, backup_path)
            logger.info(f"数据库备份完成: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"数据库备份失败 {db_path}: {e}")
            return None

    def recreate_database(self, db_path: Path) -> bool:
        """重新创建数据库文件"""
        try:
            # 备份原文件
            backup_path = self.backup_database(db_path)

            # 删除原文件
            if db_path.exists():
                db_path.unlink()

            # 创建新的空数据库
            with sqlite3.connect(str(db_path), timeout=30.0) as conn:
                try:
                    conn.execute("PRAGMA busy_timeout=30000")
                    conn.execute("PRAGMA foreign_keys=ON")
                except Exception:
                    pass
                conn.execute("SELECT 1")  # 简单测试
                conn.commit()

            # 修复权限
            self.fix_file_permissions(db_path)

            logger.info(f"重新创建数据库: {db_path}")
            if backup_path:
                logger.info(f"原数据库已备份到: {backup_path}")

            return True

        except Exception as e:
            logger.error(f"重新创建数据库失败 {db_path}: {e}")
            return False

    def scan_database_files(self) -> List[Path]:
        """扫描所有数据库文件

        只扫描应用运行期实际会被使用和需要写入测试的目录：`db` 与 `sessions`。
        明确不扫描项目根目录，避免误将 `backups/` 内的历史备份文件当作“需要修复/写入测试”的数据库，
        防止对备份文件执行连接或重建操作，从而引发
        "database disk image is malformed" 日志与递归生成 `.backup.<ts>` 文件名的问题。
        """
        db_files = []

        # 扫描常见的数据库文件位置
        search_patterns = ["*.db", "*.sqlite", "*.sqlite3", "*.session"]

        # 仅扫描会被实际使用的数据库目录
        search_dirs = [
            self.session_dir,
            self.db_dir,
        ]

        for directory in search_dirs:
            if directory.exists():
                for pattern in search_patterns:
                    db_files.extend(directory.glob(pattern))
                    # 也搜索子目录
                    db_files.extend(directory.glob(f"**/{pattern}"))

        # 去重并排序
        unique_files = list(set(db_files))
        unique_files.sort()

        logger.debug(f"发现 {len(unique_files)} 个数据库文件")
        return unique_files

    def fix_all_permissions(self) -> Tuple[int, int]:
        """修复所有数据库相关的权限问题"""
        success_count = 0
        total_count = 0

        logger.info("开始修复数据库权限问题...")

        # 1. 修复关键目录权限
        critical_dirs = [self.session_dir, self.db_dir]
        for directory in critical_dirs:
            total_count += 1
            if self.fix_directory_permissions(directory):
                success_count += 1

        # 2. 扫描并修复所有数据库文件
        db_files = self.scan_database_files()

        for db_path in db_files:
            total_count += 1

            # 检查文件权限
            file_perms = self.check_file_permissions(db_path)
            logger.debug(f"文件权限检查 {db_path}: {file_perms}")

            if not file_perms["writable"]:
                # 尝试修复文件权限
                if self.fix_file_permissions(db_path):
                    # 重新测试
                    if self.test_database_write(db_path):
                        success_count += 1
                        logger.info(f"成功修复数据库权限: {db_path}")
                    else:
                        # 权限修复失败，尝试重新创建
                        if self.recreate_database(db_path):
                            success_count += 1
                            logger.warning(f"重新创建数据库: {db_path}")
                        else:
                            logger.error(f"无法修复数据库: {db_path}")
                else:
                    logger.error(f"修复文件权限失败: {db_path}")
            else:
                # 权限正常，测试写入
                if self.test_database_write(db_path):
                    success_count += 1
                else:
                    # 写入测试失败，尝试重新创建
                    if self.recreate_database(db_path):
                        success_count += 1
                        logger.warning(f"重新创建数据库: {db_path}")
                    else:
                        logger.error(f"无法修复数据库: {db_path}")

        logger.info(f"权限修复完成: {success_count}/{total_count} 成功")
        return success_count, total_count

    def generate_report(self) -> Dict:
        """生成权限检查报告"""
        report = {
            "timestamp": time.time(),
            "directories": {},
            "files": {},
            "summary": {
                "total_dirs": 0,
                "writable_dirs": 0,
                "total_files": 0,
                "writable_files": 0,
                "issues": [],
            },
        }

        # 检查目录
        critical_dirs = [self.session_dir, self.db_dir]
        for directory in critical_dirs:
            dir_perms = self.check_directory_permissions(directory)
            report["directories"][str(directory)] = dir_perms
            report["summary"]["total_dirs"] += 1
            if dir_perms["writable"]:
                report["summary"]["writable_dirs"] += 1
            else:
                report["summary"]["issues"].append(f"目录不可写: {directory}")

        # 检查文件
        db_files = self.scan_database_files()
        for db_path in db_files:
            file_perms = self.check_file_permissions(db_path)
            report["files"][str(db_path)] = file_perms
            report["summary"]["total_files"] += 1

            if file_perms["writable"]:
                # 进一步测试数据库写入
                if self.test_database_write(db_path):
                    report["summary"]["writable_files"] += 1
                else:
                    report["summary"]["issues"].append(f"数据库不可写: {db_path}")
            else:
                report["summary"]["issues"].append(f"文件不可写: {db_path}")

        return report


# 全局实例
database_manager = DatabaseManager()


def ensure_database_permissions():
    """确保数据库权限正常，应用启动时调用"""
    try:
        success_count, total_count = database_manager.fix_all_permissions()

        if success_count == total_count:
            logger.info("所有数据库权限检查通过")
            return True
        else:
            logger.warning(f"部分数据库权限问题未解决: {success_count}/{total_count}")
            return False

    except Exception as e:
        logger.error(f"数据库权限检查失败: {e}")
        return False


def get_database_report() -> Dict:
    """获取数据库权限报告"""
    return database_manager.generate_report()
