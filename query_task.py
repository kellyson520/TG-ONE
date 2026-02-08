import sqlite3
import json

db_path = "./data/db/forward.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

query = "SELECT id, task_type, task_data, status, retry_count, last_error FROM task_queue WHERE task_data LIKE ? AND task_data LIKE ?"
params = ('%585%', '%-1002815974674%')

cursor.execute(query, params)
rows = cursor.fetchall()

for row in rows:
    print(f"ID: {row[0]}")
    print(f"Type: {row[1]}")
    print(f"Data: {row[2]}")
    print(f"Status: {row[3]}")
    print(f"Retries: {row[4]}")
    print(f"Error: {row[5]}")
    print("-" * 20)

conn.close()
