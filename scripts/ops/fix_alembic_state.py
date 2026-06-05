#!/usr/bin/env python3
"""
数据库迁移状态修复工具
解决 Alembic 版本状态与实际数据库不一致的问题
"""
import sys
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 当前最新的迁移版本
CURRENT_REVISION = "e76e90efcd4c"


def get_db_path():
    """获取数据库文件路径"""
    base_dir = Path(__file__).parent.parent.parent
    db_paths = [
        base_dir / "data" / "db" / "forward.db",
        base_dir / "db" / "forward.db",
        base_dir / "data" / "forward.db",
    ]
    
    for db_path in db_paths:
        if db_path.exists():
            return db_path
    
    # 返回默认路径（即使不存在）
    return db_paths[0]


def check_table_exists(conn, table_name):
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def check_alembic_version(conn):
    """检查 alembic_version 表状态"""
    cursor = conn.cursor()
    
    # 检查表是否存在
    if not check_table_exists(conn, "alembic_version"):
        return None, "表不存在"
    
    # 检查版本记录
    cursor.execute("SELECT version_num FROM alembic_version")
    row = cursor.fetchone()
    
    if not row:
        return None, "表为空"
    
    return row[0], "正常"


def create_alembic_version_table(conn):
    """创建 alembic_version 表"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL PRIMARY KEY
        )
    """)
    conn.commit()
    print("✅ 已创建 alembic_version 表")


def stamp_current_revision(conn, revision):
    """标记当前迁移版本"""
    cursor = conn.cursor()
    
    # 清空现有记录
    cursor.execute("DELETE FROM alembic_version")
    
    # 插入当前版本
    cursor.execute(
        "INSERT INTO alembic_version (version_num) VALUES (?)",
        (revision,)
    )
    conn.commit()
    print(f"✅ 已标记数据库迁移版本为: {revision}")


def analyze_database_state(conn):
    """分析数据库当前状态"""
    print("\n📋 数据库状态分析:")
    print("=" * 60)
    
    # 检查核心表
    core_tables = [
        "access_control_list",
        "chats",
        "forward_rules",
        "users",
        "task_queue"
    ]
    
    existing_tables = []
    missing_tables = []
    
    for table in core_tables:
        if check_table_exists(conn, table):
            existing_tables.append(table)
            # 获取记录数
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✅ {table}: {count} 条记录")
        else:
            missing_tables.append(table)
            print(f"  ❌ {table}: 不存在")
    
    print("=" * 60)
    
    return existing_tables, missing_tables


def fix_alembic_state(db_path):
    """修复 Alembic 状态"""
    print(f"\n🔧 开始修复数据库迁移状态...")
    print(f"数据库路径: {db_path}")
    
    if not db_path.exists():
        print(f"❌ 错误: 数据库文件不存在: {db_path}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(str(db_path))
        
        # 分析当前状态
        existing_tables, missing_tables = analyze_database_state(conn)
        
        # 检查 alembic_version 表
        print("\n🔍 检查迁移版本表...")
        current_version, status = check_alembic_version(conn)
        
        if status == "正常":
            print(f"  当前版本: {current_version}")
            if current_version == CURRENT_REVISION:
                print("  ✅ 数据库迁移状态正常，无需修复")
                return True
            else:
                print(f"  ⚠️ 版本不一致，将更新为: {CURRENT_REVISION}")
        elif status == "表不存在":
            print("  ❌ alembic_version 表不存在")
            create_alembic_version_table(conn)
        elif status == "表为空":
            print("  ⚠️ alembic_version 表为空")
        
        # 判断修复策略
        if len(existing_tables) >= 4:
            # 数据库已有大量表，说明是手动创建或旧版本
            print("\n📌 检测到数据库已存在核心表，采用状态同步策略...")
            stamp_current_revision(conn, CURRENT_REVISION)
            print("✅ 修复完成！数据库已标记为最新版本。")
        else:
            print("\n⚠️ 数据库结构不完整，请运行 alembic upgrade head 完成初始化")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("数据库迁移状态修复工具")
    print("=" * 60)
    
    db_path = get_db_path()
    success = fix_alembic_state(db_path)
    
    if success:
        print("\n🎉 修复成功！现在可以安全运行应用了。")
        sys.exit(0)
    else:
        print("\n❌ 修复失败，请检查错误信息。")
        sys.exit(1)


if __name__ == "__main__":
    main()
