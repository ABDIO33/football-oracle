"""Check sofa_historical_results table schema"""
import sqlite3, os, sys

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

cur = conn.execute('PRAGMA table_info(sofa_historical_results)')
cols = cur.fetchall()
print("=== sofa_historical_results schema ===")
for c in cols:
    print(f'  {c[1]:30s} {c[2]:15s} nullable={not c[3]} default={c[4]}')

print()
# Check if status_type and start_timestamp exist
cur = conn.execute("SELECT name FROM pragma_table_info('sofa_historical_results') WHERE name IN ('status_type', 'start_timestamp')")
missing = cur.fetchall()
if missing:
    for m in missing:
        print(f'Column exists: {m[0]}')
else:
    print('Neither status_type nor start_timestamp exist!')

# Try a simple query
print('\nTesting query...')
try:
    cur = conn.execute('SELECT COUNT(*) FROM sofa_historical_results')
    print(f'Total rows: {cur.fetchone()[0]}')
except Exception as e:
    print(f'Query error: {e}')

# Check the actual column names
print('\nChecking sample row...')
cur = conn.execute('SELECT * FROM sofa_historical_results LIMIT 1')
row = cur.fetchone()
if row:
    names = [d[0] for d in cur.description]
    print(f'Actual columns: {names}')

conn.close()
