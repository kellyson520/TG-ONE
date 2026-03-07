import sqlite3
import os

db_path = "data/db/hotwords.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA index_list('hot_period_stats')")
indices = cursor.fetchall()
print("Indices for hot_period_stats:")
for idx in indices:
    print(idx)
conn.close()
