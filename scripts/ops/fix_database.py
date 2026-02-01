#!/usr/bin/env python3
"""
数据库修复脚本
用于修复损坏的 SQLite 数据库文件
"""

import os
import sqlite3
import shutil
import logging
from datetime import datetime
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseFixer:
    def __init__(self, db_path="./db/forward.db"):
        base_dir = Path(__file__).resolve().parent.parent
        p = Path(db_path)
        if not p.is_absolute():
            p = (base_dir / p).resolve()
        self.db_path = p
        self.backup_dir = (base_dir / "db" / "backup").resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def check_database_integrity(self):
        """检查数据库完整性"""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("PRAGMA busy_timeout=30000")
                    cursor.execute("PRAGMA foreign_keys=ON")
                except Exception:
                    pass
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result[0] == "ok":
                    logger.info("数据库完整性检查通过")
                    return True
                else:
                    logger.error(f"数据库完整性检查失败: {result[0]}")
                    return False
        except Exception as e:
            logger.error(f"数据库完整性检查异常: {e}")
            return False
    
    def backup_corrupted_database(self):
        """备份损坏的数据库文件"""
        if not self.db_path.exists():
            logger.warning("数据库文件不存在")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"corrupted_forward_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"已备份损坏的数据库到: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"备份数据库失败: {e}")
            return None
    
    def try_recover_data(self):
        """尝试恢复数据"""
        if not self.db_path.exists():
            logger.warning("数据库文件不存在，无法恢复")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recovered_path = self.backup_dir / f"recovered_data_{timestamp}.sql"
        
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                with open(recovered_path, 'w', encoding='utf-8') as f:
                    for line in conn.iterdump():
                        f.write(f'{line}\n')
            logger.info(f"数据已导出到: {recovered_path}")
            return recovered_path
        except Exception as e:
            logger.error(f"数据恢复失败: {e}")
            return None
    
    def create_new_database(self):
        """创建新的数据库文件"""
        try:
            # 删除损坏的数据库文件
            if self.db_path.exists():
                os.remove(self.db_path)
                logger.info("已删除损坏的数据库文件")
            
            # 确保数据库目录存在
            self.db_path.parent.mkdir(exist_ok=True)
            
            # 创建新的空数据库
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                logger.info("已创建新的数据库文件")
                
                # 设置基本的 PRAGMA
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA foreign_keys=ON")
                conn.commit()
                
            return True
        except Exception as e:
            logger.error(f"创建新数据库失败: {e}")
            return False
    
    def restore_from_backup(self, backup_path):
        """从备份文件恢复数据"""
        try:
            if not Path(backup_path).exists():
                logger.error(f"备份文件不存在: {backup_path}")
                return False
                
            # 读取 SQL 备份并执行
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    conn.executescript(sql_script)
                    conn.commit()
                    
            logger.info(f"从备份恢复数据成功: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"从备份恢复数据失败: {e}")
            return False
    
    def fix_database(self):
        """修复数据库的主流程"""
        logger.info("开始数据库修复流程...")
        
        # 1. 检查数据库完整性
        if self.check_database_integrity():
            logger.info("数据库正常，无需修复")
            return True
        
        # 2. 备份损坏的数据库
        backup_path = self.backup_corrupted_database()
        
        # 3. 尝试恢复数据
        recovered_sql = self.try_recover_data()
        
        # 4. 创建新数据库
        if not self.create_new_database():
            logger.error("创建新数据库失败")
            return False
        
        # 5. 如果有恢复的数据，尝试导入
        if recovered_sql:
            if self.restore_from_backup(recovered_sql):
                logger.info("数据库修复完成，数据已恢复")
            else:
                logger.warning("数据库修复完成，但数据恢复失败")
        else:
            logger.warning("数据库修复完成，但无法恢复原有数据")
        
        # 6. 最终完整性检查
        if self.check_database_integrity():
            logger.info("修复后的数据库完整性检查通过")
            return True
        else:
            logger.error("修复后的数据库仍有问题")
            return False

def main():
    """主函数"""
    fixer = DatabaseFixer()
    
    print("=" * 50)
    print("SQLite 数据库修复工具")
    print("=" * 50)
    
    success = fixer.fix_database()
    
    if success:
        print("\n✅ 数据库修复成功！")
        print("📌 请重启应用程序以使用修复后的数据库")
    else:
        print("\n❌ 数据库修复失败！")
        print("📌 建议手动检查数据库文件或联系技术支持")
    
    print("\n备份文件保存在:", fixer.backup_dir.absolute())

if __name__ == "__main__":
    main()
