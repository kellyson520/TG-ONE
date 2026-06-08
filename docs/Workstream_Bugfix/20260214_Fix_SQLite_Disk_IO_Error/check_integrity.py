import sqlite3
import os
import sys

DB_PATH = os.path.join("data", "forwarder.db")

def check_integrity():
    print(f"Checking database at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database file not found!")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("Running PRAGMA integrity_check...")
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchall()
        print(f"Integrity Check Result: {result}")
        
        print("Running PRAGMA foreign_key_check...")
        cursor.execute("PRAGMA foreign_key_check;")
        fk_result = cursor.fetchall()
        print(f"Foreign Key Check Result: {fk_result}")
        
        # Check if we can write a dummy table
        print("Testing write operation...")
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS _test_write (id INTEGER PRIMARY KEY)")
            cursor.execute("INSERT INTO _test_write DEFAULT VALUES")
            conn.commit()
            print("Write test successful.")
            cursor.execute("DROP TABLE _test_write")
            conn.commit()
        except Exception as e:
            print(f"Write test failed: {e}")

        conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    check_integrity()
