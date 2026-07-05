"""Check DB structure"""
import sqlite3, json

conn = sqlite3.connect('scrape_cache.db')

# Check all tables
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()
print('Tables:')
for t in tables:
    name = t[0]
    cur2 = conn.execute(f'SELECT COUNT(*) FROM "{name}"')
    cnt = cur2.fetchone()[0]
    cur3 = conn.execute(f'PRAGMA table_info("{name}")')
    cols = [c[1] for c in cur3.fetchall()]
    print(f'  {name}: {cnt} rows, cols={cols[:8]}...')

# Check odds_upcoming
print('\n=== odds_upcoming (sample 3) ===')
cur = conn.execute('SELECT * FROM odds_upcoming LIMIT 3')
cols = [c[1] for c in conn.execute('PRAGMA table_info(odds_upcoming)')]
for r in cur.fetchall():
    d = dict(zip(cols, r))
    for k, v in list(d.items())[:6]:
        print(f'  {k}: {str(v)[:80]}')
    print()

# Check upcoming matches we care about
print('=== WC matches ===')
cur = conn.execute('''
    SELECT home_team, away_team, commence_time 
    FROM odds_upcoming 
    WHERE home_team IN ('France', 'Senegal', 'Jordan', 'Iraq', 'Norway', 'Algeria')
       OR away_team IN ('France', 'Senegal', 'Jordan', 'Iraq', 'Norway', 'Algeria')
    LIMIT 20
''')
for r in cur.fetchall():
    print(f'  {r[0]} vs {r[1]} @ {r[2]}')

conn.close()
