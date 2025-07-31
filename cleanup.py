import sqlite3

conn = sqlite3.connect('astrofiler.db')
conn.execute("DELETE FROM migratehistory WHERE name = '002_add_example_field'")
conn.commit()
conn.close()
print('Example migration removed from history')
