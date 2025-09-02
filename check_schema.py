import sqlite3

conn = sqlite3.connect('astrofiler.db')
cursor = conn.execute('PRAGMA table_info(fitssession)')
print('FitsSession table structure:')
for row in cursor.fetchall():
    print(f'  {row[1]} ({row[2]})')
conn.close()
