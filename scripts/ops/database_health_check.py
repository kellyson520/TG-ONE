#!/usr/bin/env python3
"""
数据库健康检查脚本
用于启动时检查数据库状态并在必要时自动修复
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# 添加项目根目录到路径
# 修正项目根目录添加到路径的逻辑
# __file__ 是 scripts/ops/database_health_check.py
# parent 是 scripts/ops
# parent.parent 是 scripts
# parent.parent.parent 是 . (项目根目录)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.ops.fix_database import DatabaseFixer

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseHealthChecker:
    def __init__(self):
        from core.config import settings
        database_url = settings.DATABASE_URL
        if database_url.startswith('sqlite'):
            # 提取路径部分
            raw_path = database_url.split('///')[-1]
            base_dir = settings.BASE_DIR
            p = Path(raw_path)
            if not p.is_absolute():
                p = (base_dir / p).resolve()
            self.db_path = p
        else:
            # 非 SQLite 数据库，跳过检查
            self.db_path = None
        
        # 缓存数据库路径
        self.cache_db_path = settings.PERSIST_CACHE_SQLITE
        
        self.fixer = DatabaseFixer(self.db_path) if self.db_path else None
        
        # 简单的缓存修复器 (不备份，直接重建)
        self.cache_fixer = DatabaseFixer(self.cache_db_path) if self.cache_db_path else None
    
    def is_sqlite_database(self):
        """检查是否为 SQLite 数据库"""
        return self.db_path is not None
    
    def check_database_exists(self):
        """检查数据库文件是否存在"""
        if not self.is_sqlite_database():
            return True  # 非 SQLite 数据库假设存在
        
        return self.db_path.exists()
    
    def check_database_accessible(self):
        """检查数据库是否可访问"""
        if not self.is_sqlite_database():
            return True  # 非 SQLite 数据库跳过检查
        
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("PRAGMA busy_timeout=30000")
                    cursor.execute("PRAGMA foreign_keys=ON")
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"数据库不可访问: {e}")
            return False
    
    def check_database_integrity(self):
        """检查数据库完整性"""
        if not self.is_sqlite_database():
            return True  # 非 SQLite 数据库跳过检查
        
        return self.fixer.check_database_integrity()

    def check_cache_health(self):
        """检查缓存数据库健康状况"""
        if not self.cache_db_path:
            return True
            
        logger.info(f"检查缓存数据库: {self.cache_db_path.name}")
        
        # 1. 检查存在性
        if not self.cache_db_path.exists():
            return True # 缓存文件不存在是正常的，会在使用时创建
            
        # 2. 检查完整性
        if not self.cache_fixer.check_database_integrity():
            logger.warning(f"⚠️ 缓存数据库损坏: {self.cache_db_path}")
            try:
                # 直接删除重建
                if self.cache_db_path.exists():
                    os.remove(self.cache_db_path)
                for ext in ["-shm", "-wal"]:
                    p = self.cache_db_path.with_suffix(self.cache_db_path.suffix + ext)
                    if p.exists():
                        os.remove(p)
                logger.info("✅ 已删除损坏的缓存数据库 (将在下次运行时自动重建)")
                return True
            except Exception as e:
                logger.error(f"❌ 无法删除缓存数据库: {e}")
                return False
        return True
    
    def perform_health_check(self):
        """执行健康检查"""
        logger.info("开始数据库健康检查...")
        
        # 0. 优先检查缓存 (因为它容易坏且容易修)
        self.check_cache_health()
        
        if not self.is_sqlite_database():
            logger.info("检测到非 SQLite 数据库，跳过健康检查")
            return True
        
        # 1. 检查文件是否存在
        if not self.check_database_exists():
            logger.warning("数据库文件不存在，将创建新数据库")
            return self.fixer.create_new_database()
        
        # 2. 检查是否可访问
        if not self.check_database_accessible():
            logger.error("数据库无法访问，需要修复")
            return self.fixer.fix_database()
        
        # 3. 检查完整性
        if not self.check_database_integrity():
            logger.error("数据库完整性检查失败，需要修复")
            return self.fixer.fix_database()
        
        logger.info("数据库健康检查通过")
        return True
    
    def auto_fix_if_needed(self):
        """如果需要则自动修复数据库"""
        if not self.perform_health_check():
            logger.error("数据库健康检查失败，程序可能无法正常运行")
            return False
        
        return True

def main():
    """主函数"""
    checker = DatabaseHealthChecker()
    
    print("🔍 执行数据库健康检查...")
    
    success = checker.auto_fix_if_needed()
    
    if success:
        print("✅ 数据库检查通过，可以正常启动")
        sys.exit(0)
    else:
        print("❌ 数据库检查失败，请手动修复后重试")
        print("🔧 建议运行: python scripts/fix_database.py")
        sys.exit(1)

if __name__ == "__main__":
    main()
