"""Generate timestamps for FD historical matches"""
import sqlite3, sys, time
from datetime import datetime
sys.path.insert(0, '.')
conn = sqlite3.connect('scrape_cache.db')

rows = conn.execute('''
    SELECT id, date FROM sofa_historical_results
    WHERE (start_timestamp IS NULL OR start_timestamp = 0)
    AND date IS NOT NULL AND date != ''
''').fetchall()
print(f'Matches without timestamps: {len(rows):,}')

fixed = 0
errors = 0
for row in rows:
    mid, date_str = row
    try:
        # Parse YYYY-MM-DD
        dt = datetime.strptime(date_str.strip(), '%Y-%m-%d')
        ts = int(dt.timestamp())
        conn.execute('UPDATE sofa_historical_results SET start_timestamp = ? WHERE id = ?', (ts, mid))
        fixed += 1
    except:
        errors += 1
    if fixed % 50000 == 0:
        conn.commit()

conn.commit()
print(f'Fixed: {fixed:,}, Errors: {errors}')
conn.close()
