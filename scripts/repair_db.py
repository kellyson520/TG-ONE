import sqlite3
import os

def repair_db(db_path):
    if not os.path.exists(db_path):
        return
    print(f"--- Attempting repair on {db_path} ---")
    try:
        # Check integrity first
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        print(f"Integrity check: {res}")
        
        # Try VACUUM
        print("Running VACUUM...")
        conn.execute("VACUUM;")
        conn.close()
        print(f"SUCCESS: {db_path} repaired/vacuumed.")
    except sqlite3.DatabaseError as e:
        print(f"CRITICAL ERROR: {db_path} is definitely malformed: {e}")
        try_recreate_entities(db_path)
    except Exception as e:
        print(f"STUPID ERROR: {e}")

def try_recreate_entities(db_path):
    print(f"Attempting to dump and recreate {db_path} (dropping entities table)...")
    # In Telethon, entities table is just a cache. 
    # Deleting it will force Telethon to re-resolve entities.
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # List tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        print(f"Tables found: {tables}")
        
        if 'entities' in tables:
            print("Dropping 'entities' table...")
            cur.execute("DROP TABLE entities;")
            conn.commit()
            print("Running VACUUM after drop...")
            conn.execute("VACUUM;")
            print("SUCCESS: table 'entities' dropped and DB vacuumed.")
        conn.close()
    except Exception as e:
        print(f"Failed to drop entities table: {e}")
        print("Final resort: You might need to delete the .session file and let the bot re-login (not recommended).")

if __name__ == "__main__":
    repair_db("sessions/user.session")
    repair_db("sessions/bot.session")
    repair_db("cache.db")
