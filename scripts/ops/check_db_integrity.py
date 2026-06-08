import sqlite3
import os

def check_integrity(db_path):
    if not os.path.exists(db_path):
        print(f"File not found: {db_path}")
        return
    print(f"Checking {db_path}...")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        print(f"Result for {db_path}: {result}")
    except Exception as e:
        print(f"Error checking {db_path}: {e}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    check_integrity("sessions/user.session")
    check_integrity("sessions/bot.session")
    check_integrity("cache.db")
