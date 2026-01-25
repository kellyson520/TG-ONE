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
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fix_database import DatabaseFixer

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseHealthChecker:
    def __init__(self):
        # 从环境变量获取数据库路径
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./db/forward.db')
        if database_url.startswith('sqlite:///'):
            raw_path = database_url.replace('sqlite:///', '')
            base_dir = Path(__file__).resolve().parent.parent
            p = Path(raw_path)
            if not p.is_absolute():
                p = (base_dir / p).resolve()
            self.db_path = p
        else:
            # 非 SQLite 数据库，跳过检查
            self.db_path = None
        
        self.fixer = DatabaseFixer(self.db_path) if self.db_path else None
    
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
                except Exception:
                    pass
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
    
    def perform_health_check(self):
        """执行健康检查"""
        logger.info("开始数据库健康检查...")
        
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
