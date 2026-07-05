"""Check odds_upcoming schema + data"""
import sqlite3
conn = sqlite3.connect('scrape_cache.db')
s = conn.execute("SELECT sql FROM sqlite_master WHERE name='odds_upcoming'").fetchone()
print(f'Schema: {s[0]}')
r = conn.execute('SELECT * FROM odds_upcoming LIMIT 3').fetchall()
for row in r:
    print(row)
c = conn.execute('SELECT COUNT(*) FROM odds_upcoming').fetchone()
print(f'Total: {c[0]}')
conn.close()
