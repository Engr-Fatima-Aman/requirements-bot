import sqlite3

conn = sqlite3.connect('requirements.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Check projects table
cursor.execute('SELECT COUNT(*) FROM projects')
count = cursor.fetchone()[0]
print(f"Projects count: {count}")

conn.close()
