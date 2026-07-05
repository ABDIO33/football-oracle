import sqlite3
conn = sqlite3.connect('scrape_cache.db')

# Check team_name_mapping
try:
    m = conn.execute('SELECT COUNT(*) FROM team_name_mapping').fetchone()[0]
    print(f'Team name mappings: {m}')
    m85 = conn.execute('SELECT COUNT(*) FROM team_name_mapping WHERE confidence >= 0.85').fetchone()[0]
    print(f'High confidence (>=0.85): {m85}')
    rows = conn.execute('SELECT * FROM team_name_mapping LIMIT 10').fetchall()
    print('Samples:', rows[:5])
except Exception as e:
    print(f'No team_name_mapping: {e}')

# All tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print(f'\nTables ({len(tables)}):')
for t in tables:
    try:
        cnt = conn.execute(f'SELECT COUNT(*) FROM "{t[0]}"').fetchone()[0]
        print(f'  {t[0]:40s} {cnt:>10,} rows')
    except Exception as e:
        print(f'  {t[0]:40s} ERROR: {e}')

# Check sofa_historical_results columns
cur = conn.execute('SELECT * FROM sofa_historical_results LIMIT 1')
cols = [d[0] for d in cur.description]
print(f'\nsofa_historical_results columns: {cols}')

conn.close()
