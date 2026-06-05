"""
数据库空间分析诊断脚本
分析每个表的记录数和占用空间
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from core.config import settings

def analyze_database():
    """分析数据库各表的大小"""
    db_path_str = settings.DB_PATH
    if not db_path_str.endswith('.db'):
        db_path = Path(db_path_str) / "forwarder.db"
    else:
        db_path = Path(db_path_str)
    
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    # 数据库文件总大小
    total_size = db_path.stat().st_size / 1024 / 1024
    print(f"📊 数据库总大小: {total_size:.2f} MB")
    print("="*80)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📋 表空间分析 (共 {len(tables)} 个表):\n")
    print(f"{'表名':<30} {'记录数':>12} {'估算大小':>15}")
    print("-"*80)
    
    table_stats = []
    
    for table in tables:
        try:
            # 获取记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            table_stats.append({
                'name': table,
                'count': count
            })
        except Exception as e:
            print(f"⚠️  {table:<30} 分析失败: {e}")
    
    # 按记录数排序
    table_stats.sort(key=lambda x: x['count'], reverse=True)
    
    for stat in table_stats:
        print(f"{stat['name']:<30} {stat['count']:>12,}")
    
    print("="*80)
    
    # 分析 TOP 占用
    print("\n🔥 TOP 5 记录数占用:")
    for i, stat in enumerate(table_stats[:5], 1):
        print(f"{i}. {stat['name']}: {stat['count']:,} 条记录")
    
    # WAL 文件检查
    wal_path = db_path.with_suffix('.db-wal')
    if wal_path.exists():
        wal_size = wal_path.stat().st_size / 1024 / 1024
        print(f"\n📄 WAL 文件大小: {wal_size:.2f} MB")
        if wal_size > 10:
            print("⚠️  WAL 文件较大，建议执行 VACUUM")
    
    # SHM 文件检查
    shm_path = db_path.with_suffix('.db-shm')
    if shm_path.exists():
        shm_size = shm_path.stat().st_size / 1024 / 1024
        print(f"📄 SHM 文件大小: {shm_size:.2f} MB")
    
    conn.close()
    
    print("\n" + "="*80)
    print("💡 优化建议:")
    print("  1. 如果 rule_logs/audit_logs/error_logs 占用大，考虑归档")
    print("  2. 如果 media_signatures 占用大，考虑清理过期指纹")
    print("  3. 执行 VACUUM 回收碎片空间")
    print("  4. 考虑启用定期清理任务")

if __name__ == "__main__":
    analyze_database()
