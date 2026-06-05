
import sqlite3
import os

DB_PATHS = [
    'data/forwarder.db',
    'data/main.db',
    'main.db',
    'forwarder.db'
]

def check_db(path):
    FULL_PATH = os.path.abspath(path)
    if not os.path.exists(FULL_PATH):
        print(f"Database not found at {FULL_PATH}")
        return

    print(f"Checking {FULL_PATH}...")
    try:
        conn = sqlite3.connect(FULL_PATH)
        cursor = conn.cursor()
        
        # Check Journal Mode
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        print(f"  Journal Mode: {mode}")
        
        # Check Tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  Tables: {tables}")
        
        # specific check for chats/forward_rules
        if 'chats' in tables and 'forward_rules' in tables:
            print("  This IS the correct database (has chats and forward_rules).")
            
            # Check Integrity
            print("  Checking integrity...")
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()[0]
            print(f"  Integrity Check: {integrity_result}")
        else:
            print("  Required tables NOT found.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"  SQLite Error: {e}")
    except Exception as e:
        print(f"  Error: {e}")
    print("-" * 20)

if __name__ == "__main__":
    for p in DB_PATHS:
        check_db(p)
